#!/usr/bin/env python3
"""
Rewrite FLAC artist tag based on filename: 'Artist - Track.flac'
"""

import re
from pathlib import Path
from mutagen.flac import FLAC

def extract_artist_from_filename(filename):
    """
    Extracts artist and title from 'Artist - Track.flac'
    """
    name = Path(filename).stem
    
    match = re.match(r"^(.*?)\s*-\s*(.*?)$", name)
    if not match:
        return None, None

    artist = match.group(1).strip()
    title = match.group(2).strip()
    return artist, title

def rewrite_artist(flac_path):
    flac_path = Path(flac_path)
    print(f"\nProcessing: {flac_path.name}")

    artist, title = extract_artist_from_filename(flac_path.name)

    if not artist:
        print("  ❌ Could not parse filename format.")
        return False

    try:
        audio = FLAC(flac_path)
        old_artist = audio.get("artist", ["<empty>"])[0]

        audio["artist"] = artist
        audio.save()

        print(f"  ✓ Artist updated: '{old_artist}' → '{artist}'")
        return True

    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False

def process_folder(folder):
    folder = Path(folder)
    flac_files = list(folder.glob("*.flac"))

    if not flac_files:
        print("No FLAC files found.")
        return

    for f in flac_files:
        rewrite_artist(f)

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python rewrite_artist_from_filename.py <file_or_folder>")
        sys.exit(1)

    path = Path(sys.argv[1])

    if path.is_file():
        rewrite_artist(path)
    else:
        process_folder(path)

