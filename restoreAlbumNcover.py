#!/usr/bin/env python3
"""
FLAC Metadata & Cover Art Fixer
Fixes incorrect album metadata and finds proper cover art
"""

import os
import sys
import requests
from pathlib import Path
import mutagen
from mutagen.flac import FLAC
from PIL import Image
import io
import argparse
import re
from collections import defaultdict

def extract_info_from_filename(filename):
    """
    Extract artist and song title from filename
    Format: Artist - Song Title.flac
    """
    name = Path(filename).stem  # Remove extension
    
    # Common patterns
    patterns = [
        r'^(.*?)\s*-\s*(.*?)$',  # Artist - Title
        r'^(.*?)\s*–\s*(.*?)$',  # Artist – Title (en dash)
        r'^(.*?)\s*\|\s*(.*?)$', # Artist | Title
    ]
    
    for pattern in patterns:
        match = re.match(pattern, name)
        if match:
            artist = match.group(1).strip()
            title = match.group(2).strip()
            
            # Clean common prefixes/suffixes
            artist = re.sub(r'^\d+\s*-\s*', '', artist)  # Remove track numbers
            title = re.sub(r'\.flac$', '', title, flags=re.IGNORECASE)
            
            return artist, title
    
    # Fallback: try to split by last dash
    if ' - ' in name:
        parts = name.rsplit(' - ', 1)
        if len(parts) == 2:
            return parts[0].strip(), parts[1].strip()
    
    return "Unknown Artist", "Unknown Title"

def search_album_by_track(artist, title):
    """
    Search for the actual album using artist and song title
    """
    print(f"  Searching album for: {artist} - {title}")
    
    # Try MusicBrainz recording search
    try:
        url = f"https://musicbrainz.org/ws/2/recording/?query=artist:{requests.utils.quote(artist)}+recording:{requests.utils.quote(title)}&fmt=json"
        response = requests.get(url, timeout=15, headers={'User-Agent': 'MetadataFixer/1.0'})
        
        if response.status_code == 200:
            data = response.json()
            recordings = data.get('recordings', [])
            
            for recording in recordings:
                # Get releases for this recording
                releases = recording.get('releases', [])
                for release in releases:
                    album_title = release.get('title', '')
                    album_artist = release.get('artist-credit', [{}])[0].get('artist', {}).get('name', '')
                    
                    if album_title and album_artist:
                        print(f"    Found: {album_artist} - {album_title}")
                        return album_artist, album_title, release.get('id')
    
    except Exception as e:
        print(f"    MusicBrainz search error: {e}")
    
    # Try iTunes search
    try:
        url = f"https://itunes.apple.com/search?term={requests.utils.quote(artist)}+{requests.utils.quote(title)}&entity=song&limit=5"
        response = requests.get(url, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            for result in data.get('results', []):
                if result.get('wrapperType') == 'track':
                    album_artist = result.get('artistName', '')
                    album_title = result.get('collectionName', '')
                    if album_artist and album_title:
                        print(f"    Found: {album_artist} - {album_title}")
                        return album_artist, album_title, None
    
    except Exception as e:
        print(f"    iTunes search error: {e}")
    
    return None, None, None

def get_cover_art(artist, album, size=500):
    """
    Get cover art for album
    """
    print(f"  Searching cover for: {artist} - {album}")
    
    # Try MusicBrainz
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
                    cover_data = cover_response.json()
                    for image in cover_data.get('images', []):
                        if image.get('front', True):
                            img_url = image['image']
                            img_response = requests.get(img_url, timeout=15)
                            if img_response.status_code == 200:
                                print("    ✓ Cover found via MusicBrainz")
                                return resize_cover(img_response.content, size)
    except Exception as e:
        print(f"    MusicBrainz cover error: {e}")
    
    # Try iTunes
    try:
        url = f"https://itunes.apple.com/search?term={requests.utils.quote(artist)}+{requests.utils.quote(album)}&entity=album&limit=1"
        response = requests.get(url, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('results'):
                art_url = data['results'][0]['artworkUrl100'].replace('100x100', f'{size}x{size}')
                img_response = requests.get(art_url, timeout=15)
                if img_response.status_code == 200:
                    print("    ✓ Cover found via iTunes")
                    return resize_cover(img_response.content, size)
    except Exception as e:
        print(f"    iTunes cover error: {e}")
    
    return None

def resize_cover(image_data, size):
    """Resize cover art"""
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
    except Exception as e:
        print(f"    Resize error: {e}")
        return image_data

def update_flac_metadata(flac_path, artist, album, title, cover_data=None):
    """
    Update FLAC file metadata
    """
    try:
        audio = FLAC(flac_path)
        
        # Update basic metadata
        audio['artist'] = artist
        audio['album'] = album
        audio['title'] = title
        
        # Add cover art if provided
        if cover_data:
            audio.clear_pictures()
            picture = mutagen.flac.Picture()
            picture.type = 3
            picture.mime = 'image/jpeg'
            picture.data = cover_data
            picture.width = 500
            picture.height = 500
            picture.depth = 24
            audio.add_picture(picture)
        
        audio.save()
        return True
        
    except Exception as e:
        print(f"    ❌ Error updating {flac_path.name}: {e}")
        return False

def process_file(flac_file, dry_run=False):
    """
    Process a single FLAC file: fix metadata and get cover art
    """
    print(f"\n🎵 Processing: {flac_file.name}")
    
    try:
        # Extract info from filename
        filename_artist, filename_title = extract_info_from_filename(flac_file.name)
        print(f"  From filename: {filename_artist} - {filename_title}")
        
        # Search for correct album info
        correct_artist, correct_album, _ = search_album_by_track(filename_artist, filename_title)
        
        if not correct_album:
            print("  ❌ Could not find album information")
            return False
        
        print(f"  ✓ Correct metadata: {correct_artist} - {correct_album} - {filename_title}")
        
        if dry_run:
            print("  🎭 DRY RUN: Would update metadata and search for cover art")
            return True
        
        # Get cover art
        cover_data = get_cover_art(correct_artist, correct_album)
        
        if not cover_data:
            print("  ⚠️  Could not find cover art")
            # Still update metadata even without cover
            cover_data = None
        
        # Update file
        if update_flac_metadata(flac_file, correct_artist, correct_album, filename_title, cover_data):
            if cover_data:
                print("  ✅ Updated metadata and cover art")
            else:
                print("  ✅ Updated metadata (no cover art)")
            return True
        else:
            print("  ❌ Failed to update file")
            return False
            
    except Exception as e:
        print(f"  ❌ Error processing file: {e}")
        return False

def process_folder(folder_path, dry_run=False):
    """
    Process all FLAC files in a folder
    """
    folder_path = Path(folder_path)
    
    print(f"\n{'='*60}")
    print(f"PROCESSING FOLDER: {folder_path}")
    print(f"{'='*60}")
    
    if not folder_path.exists():
        print("❌ Folder does not exist")
        return False
    
    flac_files = list(folder_path.glob("*.flac"))
    if not flac_files:
        print("❌ No FLAC files found")
        return False
    
    print(f"Found {len(flac_files)} FLAC files")
    
    success_count = 0
    for flac_file in flac_files:
        if process_file(flac_file, dry_run):
            success_count += 1
    
    print(f"\n📊 RESULTS: {success_count}/{len(flac_files)} files processed successfully")
    return success_count > 0

def main():
    parser = argparse.ArgumentParser(description='Fix FLAC metadata and cover art')
    parser.add_argument('path', help='Path to file or folder')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without making changes')
    parser.add_argument('--single', action='store_true', help='Process single file instead of folder')
    
    args = parser.parse_args()
    
    # Check dependencies
    try:
        import requests
        import mutagen
        from PIL import Image
    except ImportError as e:
        print("❌ Missing dependencies. Install with:")
        print("sudo pacman -S python-requests python-mutagen python-pillow")
        sys.exit(1)
    
    path = Path(args.path)
    
    if not path.exists():
        print(f"❌ Path does not exist: {path}")
        sys.exit(1)
    
    if args.single or path.is_file():
        # Process single file
        if path.suffix.lower() != '.flac':
            print("❌ Not a FLAC file")
            sys.exit(1)
        process_file(path, args.dry_run)
    else:
        # Process folder
        process_folder(path, args.dry_run)

if __name__ == "__main__":
    main()
