#!/bin/sh
# Rebuild the handwriting data for the animated logo from assets/img/logo.png.
# Writes assets/logo/logo-write.json. Debug images go to the folder given as $1 (default: a temp dir).
set -e
cd "$(dirname "$0")"
OUT=${1:-$(mktemp -d)}
python3 -I skeleton.py ../assets/img/logo.png "$OUT/skel.pkl"
python3 -I strokes.py "$OUT/skel.pkl" "$OUT/graph.pkl" > /dev/null
python3 -I separate.py ../assets/img/logo.png "$OUT/skel.pkl" "$OUT/graph.pkl" "$OUT/sep.pkl" "$OUT/layers.png"
python3 -I order.py "$OUT/sep.pkl" ../assets/img/logo.png ../assets/logo "$OUT"
echo "debug frames: $OUT/frames.png"
