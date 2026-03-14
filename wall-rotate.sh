#!/usr/bin/env bash

WALL_DIR="$HOME/Pictures/Wallpapers"
STATE_FILE="$HOME/.cache/caelestia_wall_index"
INTERVAL=3600   # seconds (30 minutes)

# Get wallpapers (sorted)
mapfile -t WALLS < <(find "$WALL_DIR" -type f \( -iname "*.jpg" -o -iname "*.png" -o -iname "*.jpeg" \) | sort)

COUNT=${#WALLS[@]}

# Exit if no wallpapers
[ "$COUNT" -eq 0 ] && exit 1

# Read last index
if [ -f "$STATE_FILE" ]; then
    INDEX=$(cat "$STATE_FILE")
else
    INDEX=0
fi

# Fix index overflow
if [ "$INDEX" -ge "$COUNT" ]; then
    INDEX=0
fi

# Set wallpaper
caelestia wallpaper -f "${WALLS[$INDEX]}"

# Save next index
echo $((INDEX + 1)) > "$STATE_FILE"

# Optional loop mode
while sleep "$INTERVAL"; do
    INDEX=$(cat "$STATE_FILE")
    if [ "$INDEX" -ge "$COUNT" ]; then
        INDEX=0
    fi

    caelestia wallpaper -f "${WALLS[$INDEX]}"
    echo $((INDEX + 1)) > "$STATE_FILE"
done
