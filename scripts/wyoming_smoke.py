"""Smoke test a running Wyoming Whistle server.

    python scripts/wyoming_smoke.py --wav clip.wav --port 10301

Sends 2 s of silence (expects an empty transcript), then the WAV in real-time
int16 chunks, and reports the time from AudioStop to the transcript.
"""
import argparse
import asyncio
import time
import wave

from wyoming.asr import Transcribe
from wyoming.audio import AudioChunk, AudioStart, AudioStop
from wyoming.client import AsyncTcpClient


async def transcribe(host, port, pcm, language, chunk_ms):
    chunk_bytes = 16000 * 2 * chunk_ms // 1000
    async with AsyncTcpClient(host, port) as client:
        await client.write_event(Transcribe(language=language).event())
        await client.write_event(
            AudioStart(rate=16000, width=2, channels=1).event())
        for i in range(0, len(pcm), chunk_bytes):
            await client.write_event(AudioChunk(
                audio=pcm[i:i + chunk_bytes], rate=16000, width=2,
                channels=1).event())
            await asyncio.sleep(chunk_ms / 1000)
        stop = time.perf_counter()
        await client.write_event(AudioStop().event())
        result = (await asyncio.wait_for(client.read_event(), 120)).data
    return (time.perf_counter() - stop) * 1000, result["text"]


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=10301)
    ap.add_argument("--wav", required=True)
    ap.add_argument("--language", default="en")
    ap.add_argument("--chunk-ms", type=int, default=100)
    args = ap.parse_args()

    flush_ms, text = await transcribe(
        args.host, args.port, b"\x00\x00" * 16000 * 2,
        args.language, args.chunk_ms)
    print(f"silence: {text!r} ({flush_ms:.0f} ms)")

    with wave.open(args.wav) as source:
        if (source.getframerate(), source.getnchannels(),
                source.getsampwidth()) != (16000, 1, 2):
            raise SystemExit("need 16 kHz mono 16-bit PCM")
        pcm = source.readframes(source.getnframes())

    flush_ms, text = await transcribe(
        args.host, args.port, pcm, args.language, args.chunk_ms)
    print(f"speech : {text!r}")
    print(f"flush  : {flush_ms:.0f} ms after AudioStop, "
          f"{len(pcm) / 32000:.2f} s audio")


if __name__ == "__main__":
    asyncio.run(main())
