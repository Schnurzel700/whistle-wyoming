"""Wyoming bridge for Cactus Whistle."""
import argparse
import asyncio
import logging
import os
import time
from pathlib import Path

import numpy as np

from wyoming.audio import AudioChunk, AudioStart, AudioStop
from wyoming.asr import Transcribe, Transcript
from wyoming.info import AsrModel, AsrProgram, Attribution, Describe, Info
from wyoming.server import AsyncEventHandler, AsyncTcpServer, async_read_event

_LOGGER = logging.getLogger("wyoming-whistle")
WHISTLE_LANGS = ("en", "de", "fr", "es", "it", "nl", "pl")
FRAME_SECONDS = 0.03
MIN_SPEECH_SECONDS = 0.3
MAX_KEYWORDS = 200


def map_lang(code: str | None, default: str = "en") -> str:
    if not code:
        return default
    c = code.replace("_", "-").split("-")[0].lower()
    return c if c in WHISTLE_LANGS else default


def find_speech(samples: np.ndarray, rate: int, floor_db: float = -50.0,
                below_peak_db: float = 30.0, above_noise_db: float = 9.0,
                pad_seconds: float = 0.25):
    """Locate speech by energy. Returns (start, end, speech_seconds) or None.

    A 30 ms frame counts as speech when it is louder than the clip noise floor
    (10th percentile) plus a margin and within 30 dB of the peak.  Trailing
    silence is what makes Whistle slow and invent words, so it gets cut.
    """
    size = max(1, int(rate * FRAME_SECONDS))
    count = len(samples) // size
    if count == 0:
        return None
    frames = samples[:count * size].reshape(count, size)
    rms = np.sqrt(np.mean(frames.astype(np.float64) ** 2, axis=1))
    levels = 20 * np.log10(np.maximum(rms, 1e-10))
    peak = float(levels.max())
    noise = float(np.percentile(levels, 10))
    threshold = max(floor_db, peak - below_peak_db,
                    min(peak - 6.0, noise + above_noise_db))
    speech = np.flatnonzero(levels > threshold)
    if len(speech) == 0:
        return None
    pad = int(rate * pad_seconds)
    start = max(0, int(speech[0]) * size - pad)
    end = min(len(samples), (int(speech[-1]) + 1) * size + pad)
    return start, end, len(speech) * FRAME_SECONDS


class WhistleHandler(AsyncEventHandler):
    def __init__(self, *args, model, default_lang="en", keywords=None,
                 transcribe_lock=None, trim=True, **kwargs):
        super().__init__(*args, **kwargs)
        self._model = model
        self._default_lang = default_lang
        self._keywords = keywords or []
        self._lock = transcribe_lock
        self._trim = trim

    async def handle_event(self, event) -> bool:
        try:
            peer = self.writer.get_extra_info("peername")
        except Exception:
            peer = None
        _LOGGER.info("event %s from %s", event.type, peer)
        if Describe.is_type(event.type):
            await self.write_event(Info(asr=[AsrProgram(
                name="whistle",
                description="Cactus Whistle 16.9MB",
                attribution=Attribution(name="Cactus Compute", url="https://cactuscompute.com/whistle"),
                version="1.0.0",
                installed=True,
                models=[AsrModel(name="whistle", description="Whistle 16.9MB",
                                 attribution=Attribution(name="Cactus", url=""),
                                 version="1.0.0",
                                 installed=True,
                                 languages=list(WHISTLE_LANGS))],
            )]).event())
            return True

        if Transcribe.is_type(event.type):
            req = Transcribe.from_event(event)
            lang = map_lang(req.language, self._default_lang)
            terms = (self._keywords + list(req.transcript_names or [])
                     + list(req.transcript_terms or []))
            keywords = list(dict.fromkeys(
                t.strip() for t in terms if t and t.strip()))[:MAX_KEYWORDS] or None
            _LOGGER.info("transcribe lang=%s(%s) keywords=%s", lang, req.language, keywords)

            rate = 16000
            width = 2
            channels = 1
            audio = bytearray()
            try:
                while True:
                    ev = await async_read_event(self.reader)
                    if ev is None:
                        return False
                    if AudioStart.is_type(ev.type):
                        s = AudioStart.from_event(ev)
                        rate, width, channels = s.rate, s.width, s.channels
                    elif AudioChunk.is_type(ev.type):
                        chunk = AudioChunk.from_event(ev).audio or b""
                        audio += chunk
                    elif AudioStop.is_type(ev.type):
                        break
            except Exception:
                _LOGGER.exception("error reading audio stream")
                return False

            if width != 2 or channels != 1:
                _LOGGER.warning("unexpected format width=%s channels=%s rate=%s", width, channels, rate)
            pcm = np.frombuffer(bytes(audio), dtype=np.int16).astype(np.float32) / 32768.0
            if rate != 16000 and len(pcm):
                # naive resample to 16k
                dur = len(pcm) / rate
                target = int(dur * 16000)
                pcm = np.interp(
                    np.linspace(0, len(pcm), target, endpoint=False),
                    np.arange(len(pcm)), pcm).astype(np.float32)
            pcm = pcm[:480000]  # 30s max
            audio_s = len(pcm) / 16000

            bounds = find_speech(pcm, 16000) if len(pcm) else None
            if bounds is None or bounds[2] < MIN_SPEECH_SECONDS:
                # Silence or a mic tap: answer empty instead of hallucinating.
                _LOGGER.info("no speech in %.2fs, empty transcript", audio_s)
                await self.write_event(Transcript(text="", language=lang).event())
                return True
            if self._trim:
                pcm = pcm[bounds[0]:bounds[1]]
            kept_s = len(pcm) / 16000

            started = time.perf_counter()
            try:
                if self._lock is not None:
                    async with self._lock:
                        res = await asyncio.to_thread(
                            self._model.transcribe, pcm,
                            language=lang, keywords=keywords)
                else:
                    res = await asyncio.to_thread(
                        self._model.transcribe, pcm,
                        language=lang, keywords=keywords)
            except Exception:
                _LOGGER.exception("transcribe failed")
                await self.write_event(Transcript(text="").event())
                return True
            elapsed_ms = (time.perf_counter() - started) * 1000
            text = ((res or {}).get("text") or "").strip()
            out_lang = (res or {}).get("language") or lang or ""
            info = res or {}
            _LOGGER.info("-> %r lang=%s audio=%.2fs kept=%.2fs ms=%.0f ttft=%.1fms tps=%.0f",
                         text, out_lang, audio_s, kept_s, elapsed_ms,
                         info.get("ttft_ms", 0), info.get("decode_tps", 0))
            await self.write_event(Transcript(text=text, language=out_lang or None).event())
            return True

        _LOGGER.debug("ignored %s", event.type)
        return True


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--uri", default="tcp://0.0.0.0:10301")
    ap.add_argument("--weights", default=str(Path.home() / "whistle-wyoming" / "whistle.cact"))
    ap.add_argument("--default-language", default="en")
    ap.add_argument("--keywords", default="",
                    help="comma separated words to bias recognition toward")
    ap.add_argument("--options-file", default=None,
                    help="HA app /data/options.json, 'language' overrides --default-language")
    ap.add_argument("--no-trim", action="store_true",
                    help="keep leading and trailing silence")
    ap.add_argument("--debug", action="store_true")
    args = ap.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)

    # Whistle class sends no per-call telemetry; this covers any other path.
    os.environ.setdefault("NEEDLE_TELEMETRY", "0")
    os.environ.setdefault("DO_NOT_TRACK", "1")

    default_lang = args.default_language
    if args.options_file:
        try:
            import json
            with open(args.options_file) as f:
                opts = json.load(f)
            if isinstance(opts, dict) and isinstance(opts.get("language"), str):
                default_lang = opts["language"]
        except (OSError, ValueError):
            pass
    _LOGGER.info("default language %s", default_lang)
    keywords = [k.strip() for k in args.keywords.split(",") if k.strip()]
    if keywords:
        _LOGGER.info("keywords %s", keywords)

    import needle
    _LOGGER.info("loading %s ...", args.weights)
    model = await asyncio.to_thread(needle.Whistle, weights=args.weights)
    _LOGGER.info("whistle ready")

    server = AsyncTcpServer.from_uri(args.uri)
    _LOGGER.info("listening %s", args.uri)
    transcribe_lock = asyncio.Lock()
    await server.run(lambda r, w: WhistleHandler(
        r, w, model=model, default_lang=default_lang, keywords=keywords,
        transcribe_lock=transcribe_lock, trim=not args.no_trim))

if __name__ == "__main__":
    asyncio.run(main())
