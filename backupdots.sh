#!/bin/bash

# --- CONFIGURATION ---

# 1. Where to save the backup?
BACKUP_DIR="$HOME/Codes/arch-dots"

# 2. WHICH folders do you want to keep? (Edit this list!)
# Only these folders from ~/.config/ will be copied.
# Everything else (like .android, Google, discord) is ignored.
folders=(
  "nvim"
  "yazi"
  "kitty"
  "fish"
  "hypr"
  "foot"
  "fastfetch"
  "btop"
  "caelestia"
  "rmpc"
  "hypr"
  "mpd"
  "mpv"
)

# 3. WHAT to exclude? (Even inside the folders above)
# This stops you from uploading massive cache files accidentally.
excludes=(
  "--exclude=.git"
  "--exclude=node_modules"
  "--exclude=__pycache__"
  "--exclude=Cache"
  "--exclude=cache"
  "--exclude=*.log"
  "--exclude=.DS_Store"
)

# --- THE LOGIC (Do not edit below) ---

# echo "🚀 Starting Smart Backup..."

# Ensure backup dir exists
mkdir -p "$BACKUP_DIR"

for folder in "${folders[@]}"; do
  SOURCE="$HOME/.config/$folder"
  DEST="$BACKUP_DIR/$folder"

  if [ -d "$SOURCE" ]; then
    echo "Syncing: $folder"
    # -a = archive mode (keeps permissions)
    # -v = verbose
    # --delete = if you delete a file in source, delete it in backup too
    # -L = follow symlinks (Critical for Caelestia!)
    rsync -avL --delete "${excludes[@]}" "$SOURCE/" "$DEST/"
  else
    echo "⚠️  Warning: $folder not found in ~/.config/"
  fi
done

# Git Push
echo "---------------------------------"
echo "octocat: Pushing to GitHub..."
cd "$BACKUP_DIR"
git add .
git commit -m "Backup: $(date '+%Y-%m-%d %H:%M')"
git push

echo "✅ Backup Complete!"
