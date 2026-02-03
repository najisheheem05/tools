#!/bin/bash

DIR="$1"

if [ -z "$DIR" ]; then
  echo "Usage: $0 <music-folder>"
  exit 1
fi

find "$DIR" -type f -iname "*.flac" | while read -r f; do
  # Check bitrate variability (lossy tends to be very stable)
  br=$(sox "$f" -n stat 2>&1 | awk '/Bit-rate/ {print int($3)}')

  # Check frequency spread
  maxf=$(sox "$f" -n stat -freq 2>&1 | awk '/Maximum frequency/ {print int($3)}')

  # Heuristic: MP3 usually cuts hard around 16–19 kHz
  if [[ -n "$maxf" && "$maxf" -le 19000 ]]; then
    echo "POSSIBLE MP3→FLAC → $f (max freq: ${maxf} Hz)"
  fi
done
