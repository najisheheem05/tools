#!/usr/bin/env python3
"""
FLAC Cover Art + Album + Album Artist Fixer
- Fixes cover art
- Fixes ALBUM
- Fixes ALBUMARTIST
- Preserves all other metadata
"""

import io
import re
import argparse
import requests
from pathlib import Path
from PIL import Image
import mutagen
from mutagen.flac import FLAC

# -------------------- FILENAME PARSING --------------------

def extract_info_from_filename(filename):
    name = Path(filename).stem

    patterns = [
        r'^(.*?)\s*-\s*(.*?)$',
        r'^(.*?)\s*–\s*(.*?)$',
        r'^(.*?)\s*\|\s*(.*?)$',
    ]

    for p in patterns:
        m = re.match(p, name)
        if m:
            return m.group(1).strip(), m.group(2).strip()

    if ' - ' in name:
        a, t = name.rsplit(' - ', 1)
        return a.strip(), t.strip()

    return "Unknown Artist", "Unknown Title"

# -------------------- MUSIC SEARCH --------------------

def search_album_by_track(artist, title):
    print(f"  Searching album for: {artist} - {title}")

    try:
        url = (
            "https://musicbrainz.org/ws/2/recording/"
            f"?query=artist:{requests.utils.quote(artist)}"
            f"+recording:{requests.utils.quote(title)}&fmt=json"
        )
        r = requests.get(url, timeout=15, headers={'User-Agent': 'FLACFixer/1.0'})

        if r.status_code == 200:
            for rec in r.json().get("recordings", []):
                for rel in rec.get("releases", []):
                    album = rel.get("title")
                    album_artist = (
                        rel.get("artist-credit", [{}])[0]
                        .get("artist", {})
                        .get("name")
                    )
                    if album:
                        if album_artist and album_artist.lower() == "various artists":
                            album_artist = artist
                        print(f"    Found: {album_artist} - {album}")
                        return album_artist, album
    except Exception as e:
        print(f"    MusicBrainz error: {e}")

    # iTunes fallback
    try:
        url = (
            "https://itunes.apple.com/search?"
            f"term={requests.utils.quote(artist)}+{requests.utils.quote(title)}"
            "&entity=song&limit=5"
        )
        r = requests.get(url, timeout=15)
        if r.status_code == 200:
            for res in r.json().get("results", []):
                album = res.get("collectionName")
                album_artist = res.get("artistName")
                if album and album_artist:
                    if album_artist.lower() == "various artists":
                        album_artist = artist
                    print(f"    Found: {album_artist} - {album}")
                    return album_artist, album
    except Exception as e:
        print(f"    iTunes error: {e}")

    return None, None

# -------------------- COVER ART --------------------

def resize_cover(data, size):
    try:
        img = Image.open(io.BytesIO(data))
        img.thumbnail((size, size), Image.Resampling.LANCZOS)

        if img.mode in ("RGBA", "LA", "P"):
            bg = Image.new("RGB", img.size, (255, 255, 255))
            img = img.convert("RGBA")
            bg.paste(img, mask=img.split()[-1])
            img = bg

        out = io.BytesIO()
        img.save(out, "JPEG", quality=90)
        return out.getvalue()
    except Exception:
        return data

def get_cover_art(artist, album, size=500):
    print(f"  Searching cover for: {artist} - {album}")

    try:
        url = (
            "https://musicbrainz.org/ws/2/release-group/"
            f"?query=artist:{requests.utils.quote(artist)}"
            f"+release:{requests.utils.quote(album)}&fmt=json"
        )
        r = requests.get(url, timeout=15, headers={'User-Agent': 'FLACFixer/1.0'})
        if r.status_code == 200:
            groups = r.json().get("release-groups", [])
            if groups:
                mbid = groups[0]["id"]
                c = requests.get(
                    f"https://coverartarchive.org/release-group/{mbid}",
                    timeout=15
                )
                if c.status_code == 200:
                    for img in c.json().get("images", []):
                        if img.get("front", True):
                            print("    ✓ Cover found (MusicBrainz)")
                            return resize_cover(
                                requests.get(img["image"], timeout=15).content,
                                size
                            )
    except Exception as e:
        print(f"    Cover MB error: {e}")

    try:
        url = (
            "https://itunes.apple.com/search?"
            f"term={requests.utils.quote(artist)}+{requests.utils.quote(album)}"
            "&entity=album&limit=1"
        )
        r = requests.get(url, timeout=15)
        if r.status_code == 200 and r.json().get("results"):
            art = r.json()["results"][0]["artworkUrl100"]
            art = art.replace("100x100", f"{size}x{size}")
            print("    ✓ Cover found (iTunes)")
            return resize_cover(requests.get(art, timeout=15).content, size)
    except Exception as e:
        print(f"    Cover iTunes error: {e}")

    return None

# -------------------- METADATA FIXES --------------------

def fix_tag(audio, key, value):
    current = audio.get(key)
    if isinstance(current, list):
        current = current[0]

    if current and current.strip().lower() == value.strip().lower():
        return False

    if key in audio:
        del audio[key]

    audio[key] = value
    return True

def update_metadata(path, album, album_artist):
    try:
        audio = FLAC(path)
        changed = False

        for k in ("ALBUM", "album"):
            if k in audio:
                del audio[k]

        for k in ("ALBUMARTIST", "albumartist", "ALBUM ARTIST", "album artist"):
            if k in audio:
                del audio[k]

        if album:
            audio["ALBUM"] = album
            changed = True

        if album_artist:
            audio["ALBUMARTIST"] = album_artist
            changed = True

        if changed:
            audio.save()

        return changed

    except Exception as e:
        print(f"    ❌ Metadata error: {e}")
        return False

def update_cover(path, cover):
    if not cover:
        return False
    try:
        audio = FLAC(path)
        audio.clear_pictures()
        pic = mutagen.flac.Picture()
        pic.type = 3
        pic.mime = "image/jpeg"
        pic.data = cover
        pic.width = pic.height = 500
        pic.depth = 24
        audio.add_picture(pic)
        audio.save()
        return True
    except Exception as e:
        print(f"    ❌ Cover save error: {e}")
        return False

# -------------------- PROCESSING --------------------

def process_file(path, dry_run=False):
    print(f"\n🎵 Processing: {path.name}")

    artist, title = extract_info_from_filename(path.name)
    album_artist, album = search_album_by_track(artist, title)

    if not album:
        print("  ❌ Album not found")
        return False

    print(f"  ✓ Album: {album_artist} - {album}")

    if dry_run:
        print("  🎭 Dry run — no changes made")
        return True

    cover_ok = update_cover(path, get_cover_art(album_artist, album))
    meta_ok = update_metadata(path, album, album_artist)

    if cover_ok:
        print("  ✅ Cover updated")
    if meta_ok:
        print("  ✅ Album + Album Artist fixed")

    return cover_ok or meta_ok

def process_folder(folder, dry_run=False):
    files = list(Path(folder).glob("*.flac"))
    if not files:
        print("❌ No FLAC files found")
        return

    ok = 0
    for f in files:
        if process_file(f, dry_run):
            ok += 1

    print(f"\n📊 {ok}/{len(files)} files modified")

# -------------------- ENTRY --------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("path", help="FLAC file or folder")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    p = Path(args.path)
    if p.is_file():
        process_file(p, args.dry_run)
    else:
        process_folder(p, args.dry_run)

if __name__ == "__main__":
    main()
