#!/bin/bash

DIR="$1"

if [ -z "$DIR" ]; then
  echo "Usage: $0 <music-folder>"
  exit 1
fi

shopt -s nullglob
cd "$DIR" || exit 1

for f in *.flac; do
  sr=$(soxi -r "$f" 2>/dev/null)
  maxf=$(sox "$f" -n stat -freq 2>&1 | awk '/Maximum frequency/ {print int($3)}')

  if [[ -n "$sr" && -n "$maxf" && "$sr" -ge 96000 && "$maxf" -le 23000 ]]; then
    mkdir -p fake-hires
    mv "$f" fake-hires/
    echo "Moved fake hi-res → $f"
  fi
done

