#!/bin/bash
set -e
DATA=/data
if [ ! -f "$DATA/whistle.cact" ]; then
  echo "downloading whistle.cact (~17MB)..."
  needle download Cactus-Compute/whistle --out "$DATA"
fi
OPTS=""
if [ -f "$DATA/options.json" ]; then
  OPTS="--options-file $DATA/options.json"
fi
exec python server.py --uri tcp://0.0.0.0:10301 --weights "$DATA/whistle.cact" $OPTS
