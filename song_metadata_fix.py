#!/usr/bin/env python3
"""
FLAC Album / Album Artist / Cover Fixer (Robust iTunes-based)

- Cleans filenames aggressively
- Uses iTunes search with validation
- Prevents tribute / instrumental / karaoke matches
- Correct album art only
"""

import io
import re
import argparse
import requests
import unicodedata
from pathlib import Path
from PIL import Image
import mutagen
from mutagen.flac import FLAC

# -------------------- SESSION --------------------

session = requests.Session()
session.headers.update({"User-Agent": "FLACFixer/5.0"})

BAD_ALBUM_WORDS = (
    "karaoke", "tribute", "piano", "instrumental",
    "covers", "cover version", "performance", "performed"
)

# -------------------- NORMALIZATION --------------------

def normalize_text(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = s.replace("’", "'").replace("“", '"').replace("”", '"')
    return s.strip()

def extract_info_from_filename(filename):
    name = Path(filename).stem

    # Remove track numbers
    name = re.sub(r'^\s*\d+\s*[\.\-\_]\s*', '', name)

    m = re.match(r'^(.*?)\s*-\s*(.*?)$', name)
    if not m:
        return None, None

    artist = normalize_text(m.group(1))
    title = normalize_text(m.group(2))

    return artist, title

def normalize_artist(artist):
    artist = artist.lower()

    artist = re.split(
        r'feat\.?|ft\.?|featuring|&|,| x | and ',
        artist
    )[0]

    return normalize_text(artist.title())

def normalize_title(title):
    # Remove brackets content
    title = re.sub(r'\(.*?\)|\[.*?\]', '', title)

    # Remove remix/version noise
    title = re.sub(
        r'\b(remix|edit|version|from.*|live)$',
        '',
        title,
        flags=re.I
    )

    return normalize_text(title)

# -------------------- ITUNES SEARCH --------------------

def is_bad_album(album):
    a = album.lower()
    return any(bad in a for bad in BAD_ALBUM_WORDS)

def is_valid_itunes_match(res, artist, title):
    track = normalize_text(res.get("trackName", "")).lower()
    artist_name = normalize_text(res.get("artistName", "")).lower()

    if artist.lower() not in artist_name:
        return False

    if title.lower() not in track:
        return False

    album = res.get("collectionName", "")
    if is_bad_album(album):
        return False

    return True

def search_itunes(artist, title):
    print("  🍎 Searching iTunes")

    queries = [
        f"{artist} {title}",
        f"{title} {artist}",
        title
    ]

    for q in queries:
        try:
            url = (
                "https://itunes.apple.com/search"
                f"?term={requests.utils.quote(q)}"
                "&entity=song&limit=10"
            )

            r = session.get(url, timeout=15)
            if r.status_code != 200:
                continue

            for res in r.json().get("results", []):
                if not is_valid_itunes_match(res, artist, title):
                    continue

                album = res.get("collectionName")
                album_artist = res.get("artistName")
                art = res.get("artworkUrl100")

                if album and album_artist and art:
                    art = art.replace("100x100", "500x500")
                    print(f"    ✓ iTunes match: {album_artist} – {album}")
                    return album_artist, album, art

        except Exception:
            continue

    return None

# -------------------- COVER --------------------

def resize_cover(data, size=500):
    img = Image.open(io.BytesIO(data))
    img.thumbnail((size, size), Image.Resampling.LANCZOS)

    if img.mode != "RGB":
        img = img.convert("RGB")

    out = io.BytesIO()
    img.save(out, "JPEG", quality=92)
    return out.getvalue()

def update_cover(path, art_url):
    try:
        data = resize_cover(session.get(art_url, timeout=15).content)
        audio = FLAC(path)
        audio.clear_pictures()

        pic = mutagen.flac.Picture()
        pic.type = 3
        pic.mime = "image/jpeg"
        pic.data = data
        pic.width = pic.height = 500
        pic.depth = 24

        audio.add_picture(pic)
        audio.save()
        return True
    except Exception as e:
        print(f"    ❌ Cover error: {e}")
        return False

# -------------------- METADATA --------------------

def update_metadata(path, album, album_artist):
    audio = FLAC(path)

    for k in list(audio.keys()):
        if k.upper().replace(" ", "") in ("ALBUM", "ALBUMARTIST"):
            del audio[k]

    audio["ALBUM"] = album.replace(" - Single", "")
    audio["ALBUMARTIST"] = album_artist
    audio.save()
    return True

# -------------------- PROCESS --------------------

def process_file(path, dry_run=False):
    print(f"\n🎵 Processing: {path.name}")

    artist, title = extract_info_from_filename(path.name)
    if not artist or not title:
        print("  ❌ Filename not parseable")
        return False

    artist = normalize_artist(artist)
    title = normalize_title(title)

    match = search_itunes(artist, title)
    if not match:
        print("  ❌ No valid match found")
        return False

    album_artist, album, art_url = match

    if dry_run:
        print("  🎭 Dry run — no changes made")
        return True

    cover_ok = update_cover(path, art_url)
    meta_ok = update_metadata(path, album, album_artist)

    if cover_ok:
        print("  ✅ Cover updated")
    if meta_ok:
        print("  ✅ Album + Album Artist updated")

    return True

def process_folder(folder, dry_run=False):
    files = list(Path(folder).glob("*.flac"))
    if not files:
        print("❌ No FLAC files found")
        return

    ok = 0
    for f in files:
        if process_file(f, dry_run):
            ok += 1

    print(f"\n📊 {ok}/{len(files)} files processed")

# -------------------- ENTRY --------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("path")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    p = Path(args.path)
    if p.is_file():
        process_file(p, args.dry_run)
    else:
        process_folder(p, args.dry_run)

if __name__ == "__main__":
    main()
