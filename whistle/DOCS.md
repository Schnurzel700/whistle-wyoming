# Whistle STT app

Wyoming speech-to-text with Cactus Whistle (16.9 MB, CPU). Languages: en, de, fr, es, it, nl, pl.

First start downloads `whistle.cact` (~17 MB) into app data, then listens on port 10301. The app publishes itself to the Supervisor, so the Wyoming integration discovers it automatically; otherwise add it manually on port 10301. Set the pipeline STT to Whistle.

## Options

- `language`: fallback when the client sends no language or an unsupported one. `en`, `de`, `fr`, `es`, `it`, `nl`, `pl`. Default `en`.
- `keywords`: comma separated words to bias recognition toward, for example `Wetter,Licht,Temperatur,Flurlicht`. Use the language you speak in. Command verbs (`schalte`, `mach`, `stelle`) help more than device names.

## Behaviour

- Leading and trailing silence is trimmed before inference. Quiet clips get faster and stop producing invented words; clips under 0.3 s of speech return an empty transcript.
- Audio is converted from 16-bit PCM to the float32 samples Whistle expects.
- Telemetry is disabled; the `Whistle` class is used directly and no per-call network calls are made.
- One transcription runs at a time; concurrent requests wait for the lock.
