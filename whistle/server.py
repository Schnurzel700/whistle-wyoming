"""Wyoming bridge for Cactus Whistle."""
import argparse
import asyncio
import logging
from pathlib import Path

import numpy as np

from wyoming.audio import AudioChunk, AudioStart, AudioStop
from wyoming.asr import Transcribe, Transcript
from wyoming.info import AsrModel, AsrProgram, Attribution, Describe, Info
from wyoming.server import AsyncEventHandler, AsyncTcpServer, async_read_event

_LOGGER = logging.getLogger("wyoming-whistle")
WHISTLE_LANGS = ("en", "de", "fr", "es", "it", "nl", "pl")

def map_lang(code: str | None) -> str | None:
    if not code:
        return None
    c = code.replace("_", "-").split("-")[0].lower()
    return c if c in WHISTLE_LANGS else None

class WhistleHandler(AsyncEventHandler):
    def __init__(self, *args, model, **kwargs):
        super().__init__(*args, **kwargs)
        self._model = model

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
            lang = map_lang(req.language)
            keywords = list((req.transcript_names or []) + (req.transcript_terms or [])) or None
            _LOGGER.info("transcribe lang=%s(%s) keywords=%s", lang, req.language, keywords)

            rate = 16000
            width = 2
            channels = 1
            audio = bytearray()
            while True:
                ev = await async_read_event(self.reader)
                if ev is None:
                    return False
                if AudioStart.is_type(ev.type):
                    s = AudioStart.from_event(ev)
                    rate, width, channels = s.rate, s.width, s.channels
                elif AudioChunk.is_type(ev.type):
                    audio += AudioChunk.from_event(ev).audio
                elif AudioStop.is_type(ev.type):
                    break

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
            if len(pcm) == 0:
                await self.write_event(Transcript(text="").event())
                return True
            try:
                res = await asyncio.to_thread(
                    self._model.transcribe, pcm,
                    language=lang, keywords=keywords)
            except Exception:
                _LOGGER.exception("transcribe failed")
                await self.write_event(Transcript(text="").event())
                return True
            text = (res.get("text") or "").strip()
            out_lang = res.get("language") or lang or ""
            _LOGGER.info("-> %r lang=%s ttft=%.1fms tps=%.0f",
                         text, out_lang, res.get("ttft_ms", 0), res.get("decode_tps", 0))
            await self.write_event(Transcript(text=text, language=out_lang or None).event())
            return True

        _LOGGER.debug("ignored %s", event.type)
        return True

async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--uri", default="tcp://0.0.0.0:10300")
    ap.add_argument("--weights", default=str(Path.home() / "whistle-wyoming" / "whistle.cact"))
    ap.add_argument("--debug", action="store_true")
    args = ap.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)

    import needle
    _LOGGER.info("loading %s ...", args.weights)
    model = await asyncio.to_thread(needle.Whistle, weights=args.weights)
    _LOGGER.info("whistle ready")

    server = AsyncTcpServer.from_uri(args.uri)
    _LOGGER.info("listening %s", args.uri)
    await server.run(lambda r, w: WhistleHandler(r, w, model=model))

if __name__ == "__main__":
    asyncio.run(main())
