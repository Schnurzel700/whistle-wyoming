#!/bin/bash
set -e
DATA=/data
if [ ! -f "$DATA/whistle.cact" ]; then
  echo "downloading whistle.cact (~17MB)..."
  needle download Cactus-Compute/whistle --out "$DATA"
fi
exec python server.py --uri tcp://0.0.0.0:10301 --weights "$DATA/whistle.cact"
