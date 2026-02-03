#!/bin/bash

DIR="$1"

if [ -z "$DIR" ]; then
  echo "Usage: $0 <music-folder>"
  exit 1
fi

find "$DIR" -type f -iname "*.flac" | while read -r f; do
  sr=$(soxi -r "$f" 2>/dev/null)

  if [[ -n "$sr" && "$sr" -ge 96000 ]]; then
    echo "$f"
  fi
done

