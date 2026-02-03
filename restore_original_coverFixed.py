#!/usr/bin/env python3
"""
FLAC Cover Art Fixer
Finds and adds proper cover art WITHOUT modifying existing metadata
"""

import os
import sys
import requests
from pathlib import Path
import mutagen
from mutagen.flac import FLAC
import io
import argparse
import re
from PIL import Image

def extract_info_from_filename(filename):
    name = Path(filename).stem

    patterns = [
        r'^(.*?)\s*-\s*(.*?)$',  
        r'^(.*?)\s*–\s*(.*?)$',  
        r'^(.*?)\s*\|\s*(.*?)$', 
    ]
    
    for pattern in patterns:
        match = re.match(pattern, name)
        if match:
            artist = match.group(1).strip()
            title = match.group(2).strip()
            artist = re.sub(r'^\d+\s*-\s*', '', artist)
            title = re.sub(r'\.flac$', '', title, flags=re.IGNORECASE)
            return artist, title

    if ' - ' in name:
        parts = name.rsplit(' - ', 1)
        return parts[0].strip(), parts[1].strip()

    return "Unknown Artist", "Unknown Title"

def search_album_by_track(artist, title):
    print(f"  Searching album for: {artist} - {title}")
    
    # === MUSICBRAINZ ===
    try:
        url = f"https://musicbrainz.org/ws/2/recording/?query=artist:{requests.utils.quote(artist)}+recording:{requests.utils.quote(title)}&fmt=json"
        response = requests.get(url, timeout=15, headers={'User-Agent': 'MetadataFixer/1.0'})
        
        if response.status_code == 200:
            data = response.json()
            recordings = data.get('recordings', [])
            
            for recording in recordings:
                releases = recording.get('releases', [])
                for release in releases:
                    album_title = release.get('title', '')
                    album_artist = release.get('artist-credit', [{}])[0].get('artist', {}).get('name', '')

                    if album_title:
                        # DO NOT allow "Various Artists" to overwrite track artist
                        if album_artist.lower() == "various artists":
                            album_artist = artist  

                        print(f"    Found: {album_artist} - {album_title}")
                        return album_artist, album_title, release.get('id')
    
    except Exception as e:
        print(f"    MusicBrainz error: {e}")

    # === ITUNES ===
    try:
        url = f"https://itunes.apple.com/search?term={requests.utils.quote(artist)}+{requests.utils.quote(title)}&entity=song&limit=5"
        response = requests.get(url, timeout=15)
        
        if response.status_code == 200:
            for result in response.json().get('results', []):
                if result.get('wrapperType') == 'track':
                    album_title = result.get('collectionName', '')
                    album_artist = result.get('artistName', '')

                    if album_artist.lower() == "various artists":
                        album_artist = artist  

                    if album_artist and album_title:
                        print(f"    Found: {album_artist} - {album_title}")
                        return album_artist, album_title, None

    except Exception as e:
        print(f"    iTunes error: {e}")

    return None, None, None

def get_cover_art(artist, album, size=500):
    print(f"  Searching cover for: {artist} - {album}")
    
    # === MUSICBRAINZ COVER ===
    try:
        url = f"https://musicbrainz.org/ws/2/release-group/?query=artist:{requests.utils.quote(artist)}+release:{requests.utils.quote(album)}&fmt=json"
        response = requests.get(url, timeout=15, headers={'User-Agent': 'MetadataFixer/1.0'})
        
        if response.status_code == 200:
            data = response.json()
            release_groups = data.get('release-groups', [])
            if release_groups:
                mb_id = release_groups[0]['id']
                cover_url = f"https://coverartarchive.org/release-group/{mb_id}"
                cover_response = requests.get(cover_url, timeout=15)
                
                if cover_response.status_code == 200:
                    for image in cover_response.json().get('images', []):
                        if image.get('front', True):
                            img_url = image['image']
                            img_response = requests.get(img_url, timeout=15)
                            if img_response.status_code == 200:
                                print("    ✓ Cover found via MusicBrainz")
                                return resize_cover(img_response.content, size)
    except Exception as e:
        print(f"    Cover MB error: {e}")
    
    # === ITUNES COVER ===
    try:
        url = f"https://itunes.apple.com/search?term={requests.utils.quote(artist)}+{requests.utils.quote(album)}&entity=album&limit=1"
        response = requests.get(url, timeout=15)
        
        if response.status_code == 200:
            results = response.json().get('results', [])
            if results:
                art_url = results[0]['artworkUrl100'].replace('100x100', f'{size}x{size}')
                img_response = requests.get(art_url, timeout=15)
                if img_response.status_code == 200:
                    print("    ✓ Cover found via iTunes")
                    return resize_cover(img_response.content, size)
    except Exception as e:
        print(f"    Cover iTunes error: {e}")
    
    return None

def resize_cover(image_data, size):
    try:
        img = Image.open(io.BytesIO(image_data))
        img.thumbnail((size, size), Image.Resampling.LANCZOS)
        
        output = io.BytesIO()
        if img.mode in ('RGBA', 'LA', 'P'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
            img = background
        
        img.save(output, format='JPEG', quality=90)
        return output.getvalue()
    except:
        return image_data

def update_flac_cover(flac_path, cover_data=None):
    """Only updates cover art, preserves all existing metadata"""
    try:
        audio = FLAC(flac_path)

        if cover_data:
            # Clear existing pictures and add new one
            audio.clear_pictures()
            picture = mutagen.flac.Picture()
            picture.type = 3  # Front cover
            picture.mime = 'image/jpeg'
            picture.data = cover_data
            picture.width = 500
            picture.height = 500
            picture.depth = 24
            audio.add_picture(picture)
            audio.save()
            return True
        else:
            print("    ⚠️ No cover data to update")
            return False

    except Exception as e:
        print(f"    ❌ Error saving {flac_path.name}: {e}")
        return False

def process_file(flac_file, dry_run=False):
    print(f"\n🎵 Processing: {flac_file.name}")

    filename_artist, filename_title = extract_info_from_filename(flac_file.name)
    print(f"  From filename: {filename_artist} - {filename_title}")

    album_artist, album, _ = search_album_by_track(filename_artist, filename_title)

    if not album:
        print("  ❌ No album found")
        return False

    # album_artist fallback
    if not album_artist:
        album_artist = filename_artist

    print(f"  ✓ Found album: {album_artist} - {album}")

    if dry_run:
        print("  🎭 Dry run — no changes made")
        return True

    cover_data = get_cover_art(album_artist, album)

    ok = update_flac_cover(flac_file, cover_data=cover_data)

    if ok:
        print("  ✅ Cover art updated successfully (metadata preserved)")
    else:
        print("  ❌ Failed to update cover art")

    return ok

def process_folder(folder_path, dry_run=False):
    folder_path = Path(folder_path)

    print(f"\n========== PROCESSING FOLDER: {folder_path} ==========\n")

    flac_files = list(folder_path.glob("*.flac"))
    if not flac_files:
        print("❌ No FLAC files found")
        return False

    success = 0
    for f in flac_files:
        if process_file(f, dry_run):
            success += 1

    print(f"\n📊 RESULTS: {success}/{len(flac_files)} files updated")
    return success > 0

def main():
    parser = argparse.ArgumentParser(description='Add cover art to FLAC files without modifying metadata')
    parser.add_argument('path', help='Path to FLAC file or folder')
    parser.add_argument('--dry-run', action='store_true', help='Test without making changes')
    parser.add_argument('--single', action='store_true', help='Process single file')
    args = parser.parse_args()

    path = Path(args.path)

    if args.single or path.is_file():
        process_file(path, args.dry_run)
    else:
        process_folder(path, args.dry_run)

if __name__ == "__main__":
    main()

