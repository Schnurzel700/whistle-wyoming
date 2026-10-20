# Whistle Wyoming

Home Assistant app for [Cactus Whistle](https://cactuscompute.com/whistle) speech-to-text over the [Wyoming protocol](https://github.com/OHF-Voice/wyoming).

16.9 MB, CPU-only, languages: en, de, fr, es, it, nl, pl. Built for amd64 and aarch64.

## Install

Add `https://github.com/Schnurzel700/whistle-wyoming` as a repository in the Home Assistant App Store, install **Whistle STT**, and start it. The first start downloads the model (~17 MB). The app announces itself to the Supervisor, so the Wyoming integration should discover it; otherwise add it manually on port `10301`.

Then pick `whistle` as the speech-to-text engine in your Assist pipeline.

## Options

| Option | Default | Meaning |
| --- | --- | --- |
| `language` | `en` | Fallback language when the client sends none or an unsupported code (`en`, `de`, `fr`, `es`, `it`, `nl`, `pl`). |
| `keywords` | empty | Comma separated words to bias recognition toward, e.g. `Wetter,Licht,Temperatur`. |
| `streaming` | `false` | Run `Whistle.stream` while audio arrives. Experimental: measured slower than the trimmed batch path on CPU. |

## What the server does

```
[HA Assist] --Wyoming tcp:10301--> [server.py] --> [Whistle CPU] --> Transcript
```

- Buffers `AudioStart` / `AudioChunk` / `AudioStop`, trims leading and trailing silence by energy (noise floor + peak relative), then transcribes once.
- Maps HA language tags (`de-DE` -> `de`); unsupported codes fall back to the configured language.
- Merges the `keywords` option with any `transcript_names` / `transcript_terms` the client sends (deduplicated, capped at 200).
- Converts 16-bit PCM to float32 in [-1, 1], resamples to 16 kHz if needed, caps at 30 s.
- Returns an empty transcript for silence or clips with less than 0.3 s of speech instead of letting the model invent words.
- Serializes inference with a lock and runs it in a worker thread, so multiple connections cannot corrupt the native engine.
- Uses the `Whistle` class directly and sets `NEEDLE_TELEMETRY=0`; no per-call network calls.

## Benchmarks

Desktop 8-core, 16 kHz mono, 100 ms chunks, time from `AudioStop` to transcript:

| Clip | Batch, trimmed | Streaming |
| --- | --- | --- |
| 2 s speech + 6 s silence | 0.41 s | 6.05 s |
| 3 s speech + 8 s silence | 0.57 s | 18.17 s |
| 7.4 s continuous speech | 1.92 s | 7.52 s |

`Whistle.stream` reprocesses the buffered audio on every pass, so it cannot keep up here. Trimming is the real win: 5-6x against untrimmed audio.

## Repo layout

- `whistle/server.py`: Wyoming bridge.
- `whistle/run.sh`: bashio entrypoint, options, model download, Supervisor discovery.
- `whistle/config.yaml`: app metadata and options.
- `whistle/Dockerfile`: HA base image, Python venv, no system extras.

## Verification

Local run without Home Assistant:

```sh
python -m venv /tmp/whistle && /tmp/whistle/bin/pip install -r whistle/requirements.txt
/tmp/whistle/bin/python whistle/server.py --weights /path/to/whistle.cact --keywords "Wetter,Licht"
```

Send a `Describe` event to port 10301 and expect an `Info` event with `whistle` and the seven languages. Or run the smoke test against a live server:

```sh
python scripts/wyoming_smoke.py --wav clip.wav --port 10301
```

It sends 2 s of silence (expects an empty transcript), then the WAV in real-time chunks and prints the transcript plus the time from `AudioStop` to the result.
