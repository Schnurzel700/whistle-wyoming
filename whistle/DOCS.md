# Whistle STT app

Wyoming speech-to-text with Cactus Whistle (16.9 MB, CPU). Languages: en, de, fr, es, it, nl, pl.

First start downloads `whistle.cact` (~17 MB) into app data, then listens on port 10301. The app announces itself via Zeroconf, so the Wyoming integration should discover it automatically; otherwise add it manually on port 10301. Set the pipeline STT to Whistle.
