#!/usr/bin/env python3
"""
Script to update the genre metadata tag of audio files in a music library,
using the genre folder name from their path.

- Traverses specified music directories individually
- Supports all major Mutagen-supported audio formats
- Uses mutagen for metadata editing
- Logs updated files, errors, and permission fixes
- Efficient: skips files already tagged correctly, parallelizes processing
- Configurable via command-line arguments

Requirements:
    pip install mutagen tqdm argparse

Usage:
    python3 tag_genre_by_folder.py [options]

Options:
    --music-base PATH       Base music directory (default: /srv/dev-disk-by-uuid-c8158ed6-b7f4-4aab-9958-b0f3002b01aa/Media/Audio/Music/Sources)
    --managed PATH          Managed music directory (default: <music_base>/Managed)
    --unmanaged PATH        Unmanaged music directory (default: <music_base>/Unmanaged)
    --additional PATH       Additional music directory to process
    --cpu-limit N           Limit CPU usage to N cores
    --dry-run               Show what would be changed without making changes
    --backup                Create backups of modified files (.bak extension)
    --genre GENRE           Only process files in folders matching this genre
    --batch-size N          Process files in batches of N (default: 1000)
    --verbose               Show more detailed output
    --log-file PATH         Path to log file (default: genre_tagging.log)
"""

import os
import sys
import logging
import traceback
import argparse
import shutil
import re
from datetime import datetime
from pathlib import Path
from functools import partial
from multiprocessing import Pool, cpu_count
from typing import Dict, Tuple, List, Optional, Callable, Any, Union, Generator
try:
    from tqdm import tqdm
    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False
    print("tqdm not available. Install with: pip install tqdm")

import mutagen
from mutagen.easyid3 import EasyID3
from mutagen.mp3 import MP3
from mutagen.flac import FLAC
from mutagen.mp4 import MP4
from mutagen.oggvorbis import OggVorbis
from mutagen.oggopus import OggOpus
from mutagen.oggflac import OggFLAC
from mutagen.musepack import Musepack
from mutagen.monkeysaudio import MonkeysAudio
from mutagen.wavpack import WavPack
from mutagen.trueaudio import TrueAudio
from mutagen.asf import ASF  # For WMA
from mutagen.aiff import AIFF
from mutagen.wave import WAVE
from mutagen.optimfrog import OptimFROG
# from mutagen.spx import OggSpeex  # REMOVE THIS LINE
from mutagen.tak import TAK
from mutagen.dsf import DSF
from mutagen.dsdiff import DSDIFF


# Default paths
DEFAULT_MUSIC_BASE = "/srv/dev-disk-by-uuid-c8158ed6-b7f4-4aab-9958-b0f3002b01aa/Media/Audio/Music/Sources"

# Supported extensions (all Mutagen-supported audio formats)
AUDIO_EXTS = {
    ".mp3", ".flac", ".mp4", ".m4a", ".m4b", ".aac", ".ogg", ".opus", ".oga", ".mpc", ".ape",
    ".wv", ".tta", ".wma", ".aiff", ".aif", ".wav", ".ofr", ".ofs", ".tak", ".dsf",
    ".dff", ".au", ".mp2", ".acm"
}

# Format handlers for genre tags
# Each entry: (AudioClass, tag_key, current_value_getter, new_value_setter)
FORMAT_HANDLERS = {
    ".flac": (FLAC, "genre", lambda a, g: g, lambda a, g: [g]),
    ".mp3": (EasyID3, "genre", lambda a, g: g, lambda a, g: g),
    ".mp4": (MP4, "\xa9gen", lambda a, g: g, lambda a, g: [g]),
    ".m4a": (MP4, "\xa9gen", lambda a, g: g, lambda a, g: [g]),
    ".m4b": (MP4, "\xa9gen", lambda a, g: g, lambda a, g: [g]),
    ".aac": (MP4, "\xa9gen", lambda a, g: g, lambda a, g: [g]),
    ".ogg": (OggVorbis, "genre", lambda a, g: g, lambda a, g: [g]),
    ".opus": (OggOpus, "genre", lambda a, g: g, lambda a, g: [g]),
    ".oga": (OggFLAC, "genre", lambda a, g: g, lambda a, g: [g]),
    ".mpc": (Musepack, "genre", lambda a, g: g, lambda a, g: [g]),
    ".ape": (MonkeysAudio, "genre", lambda a, g: g, lambda a, g: [g]),
    ".wv": (WavPack, "genre", lambda a, g: g, lambda a, g: [g]),
    ".tta": (TrueAudio, "genre", lambda a, g: g, lambda a, g: [g]),
    ".wma": (ASF, "WM/Genre", lambda a, g: g, lambda a, g: [g]),
    ".aiff": (AIFF, "TCON", lambda a, g: g, lambda a, g: [g]),
    ".aif": (AIFF, "TCON", lambda a, g: g, lambda a, g: [g]),
    ".wav": (WAVE, "TCON", lambda a, g: g, lambda a, g: [g]),
    ".ofr": (OptimFROG, "genre", lambda a, g: g, lambda a, g: [g]),
    ".ofs": (OptimFROG, "genre", lambda a, g: g, lambda a, g: [g]),
    ".tak": (TAK, "genre", lambda a, g: g, lambda a, g: [g]),
    ".dsf": (DSF, "TCON", lambda a, g: g, lambda a, g: [g]),
    ".dff": (DSDIFF, "TCON", lambda a, g: g, lambda a, g: [g]),
    ".mp2": (EasyID3, "genre", lambda a, g: g, lambda a, g: g),
}

# ----------- UTILITY FUNCTIONS ------------

def setup_logging(log_file: str, verbose: bool = False) -> None:
    """Set up logging configuration."""
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )

def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Update audio file genre tags based on folder structure")

    parser.add_argument("--music-base", type=str, default=DEFAULT_MUSIC_BASE,
                        help=f"Base music directory (default: {DEFAULT_MUSIC_BASE})")
    parser.add_argument("--managed", type=str, help="Managed music directory (default: <music_base>/Managed)")
    parser.add_argument("--unmanaged", type=str, help="Unmanaged music directory (default: <music_base>/Unmanaged)")
    parser.add_argument("--additional", type=str, action="append", help="Additional music directories to process")
    parser.add_argument("--cpu-limit", type=int, help="Limit CPU usage to N cores")
    parser.add_argument("--dry-run", action="store_true", help="Show changes without modifying files")
    parser.add_argument("--backup", action="store_true", help="Create backups of modified files")
    parser.add_argument("--genre", type=str, help="Only process files in folders matching this genre")
    parser.add_argument("--batch-size", type=int, default=1000, help="Process files in batches of N (default: 1000)")
    parser.add_argument("--verbose", action="store_true", help="Show more detailed output")
    parser.add_argument("--log-file", type=str, default="genre_tagging.log", help="Path to log file")

    args = parser.parse_args()

    # Set default paths if not provided
    if not args.managed:
        args.managed = os.path.join(args.music_base, "Managed")
    if not args.unmanaged:
        args.unmanaged = os.path.join(args.music_base, "Unmanaged")

    return args

def normalize_genre(genre: str) -> str:
    """Normalize genre names for consistency."""
    # Remove leading/trailing whitespace
    genre = genre.strip()

    # Capitalize first letter of each word, but preserve specific capitalizations
    words_to_preserve = {'DJ', 'MC', 'UK', 'US', 'R&B', 'A&R', 'EDM', 'IDM', 'DnB', 'D&B',
                        'J-Pop', 'K-Pop', 'EMD'}

    result = []
    for word in genre.split():
        if word.upper() in words_to_preserve:
            result.append(word.upper())
        else:
            result.append(word.capitalize())

    return ' '.join(result)

def get_genre_from_path(path: Path, base_folder: str) -> Optional[str]:
    """
    Extract genre folder name from file path, based on known structure.
    Example: /base/Managed/Rock - Goth/Joy Division/.../track.flac -> "Rock - Goth"
    """
    try:
        parts = path.relative_to(base_folder).parts
        if not parts:
            return None
        genre = parts[0]
        return normalize_genre(genre)
    except Exception as e:
        logging.error(f"Failed to get genre from path {path}: {e}")
        return None

def backup_file(file_path: Path) -> bool:
    """Create a backup of the file with .bak extension."""
    try:
        backup_path = str(file_path) + ".bak"
        if not os.path.exists(backup_path):
            shutil.copy2(file_path, backup_path)
        return True
    except Exception as e:
        logging.error(f"Failed to create backup of {file_path}: {e}")
        return False

def set_genre_tag(file_path: Path, genre: str, dry_run: bool = False, make_backup: bool = False) -> bool:
    """
    Set the genre metadata tag for a given audio file.
    Returns True if file was updated, False otherwise.
    """
    ext = file_path.suffix.lower()

    # Skip unsupported formats
    if ext not in FORMAT_HANDLERS:
        if ext in {".au", ".acm"}:
            logging.warning(f"{ext} format: genre tagging not supported for {file_path}")
        else:
            logging.warning(f"Unsupported audio file type for tagging: {file_path}")
        return False

    AudioClass, tag_key, getter, setter = FORMAT_HANDLERS[ext]

    try:
        # Special case for MP3
        if ext == ".mp3":
            try:
                audio = AudioClass(str(file_path))
            except Exception:
                if dry_run:
                    return True  # Would need to add tags
                audiofile = MP3(str(file_path))
                audiofile.add_tags()
                audiofile.save()
                audio = AudioClass(str(file_path))
        else:
            audio = AudioClass(str(file_path))

        # Get current genre value based on format
        current_genre = None
        if hasattr(audio, "get"):
            current_tag = audio.get(tag_key, [None])[0]
            current_genre = getter(audio, current_tag)
        elif hasattr(audio, "tags") and audio.tags:
            current_tag = audio.tags.get(tag_key, [None])[0]
            current_genre = getter(audio, current_tag)

        # Skip if already correct
        if current_genre == genre:
            return False

        # In dry run mode, just report the would-be change
        if dry_run:
            logging.info(f"Would update genre: {file_path} - '{current_genre}' → '{genre}'")
            return True

        # Create backup if requested
        if make_backup:
            backup_file(file_path)

        # Set genre tag appropriately for the format
        if hasattr(audio, "tags"):
            audio.tags[tag_key] = setter(audio, genre)
        else:
            audio[tag_key] = setter(audio, genre)

        audio.save()
        return True

    except PermissionError:
        # Try to fix permissions and retry
        if dry_run:
            logging.info(f"Would fix permissions on: {file_path}")
            return True

        try:
            os.chmod(file_path, 0o664)  # rw-rw-r--
            return set_genre_tag(file_path, genre, dry_run, make_backup)
        except Exception as perm_e:
            logging.error(f"Permission error on {file_path}: {perm_e}")
            return False
    except Exception as e:
        logging.error(f"Error updating {file_path}: {e}")
        logging.debug(traceback.format_exc())
        return False

def process_file(args: Tuple[Path, str, bool, bool, Optional[str]]) -> Tuple[str, str]:
    """Worker for multiprocessing pool."""
    file_path, base_folder, dry_run, make_backup, filter_genre = args

    genre = get_genre_from_path(file_path, base_folder)
    if not genre:
        return (str(file_path), "Genre not found")

    # Apply genre filter if specified
    if filter_genre and filter_genre.lower() not in genre.lower():
        return (str(file_path), "Skipped (genre filter)")

    updated = set_genre_tag(file_path, genre, dry_run, make_backup)
    if updated:
        return (str(file_path), f"Genre set to '{genre}'")
    else:
        return (str(file_path), "Already correct or failed")

def find_audio_files(root_folder: str) -> Generator[Path, None, None]:
    """Recursively yield all supported audio files under root_folder."""
    for dirpath, _, filenames in os.walk(root_folder):
        for fname in filenames:
            ext = os.path.splitext(fname)[1].lower()
            if ext in AUDIO_EXTS:
                yield Path(os.path.join(dirpath, fname))

def process_files_in_batches(files_and_args: List[Tuple], batch_size: int, num_workers: int) -> None:
    """Process files in batches to manage memory usage."""
    total_files = len(files_and_args)
    logging.info(f"Processing {total_files} audio files in batches of {batch_size}...")

    # Set up progress bar if tqdm is available
    if TQDM_AVAILABLE:
        pbar = tqdm(total=total_files, desc="Tagging files")

    # Process in batches
    for i in range(0, total_files, batch_size):
        batch = files_and_args[i:i+batch_size]

        with Pool(num_workers) as pool:
            results = pool.map(process_file, batch)

            for fpath, result in results:
                if "Genre set to" in result:
                    logging.info(f"{fpath}: {result}")
                elif "Already correct" in result:
                    logging.debug(f"{fpath}: {result}")
                elif "Skipped" in result:
                    logging.debug(f"{fpath}: {result}")
                else:
                    logging.warning(f"{fpath}: {result}")

                # Update progress bar
                if TQDM_AVAILABLE:
                    pbar.update(1)

    # Close progress bar
    if TQDM_AVAILABLE:
        pbar.close()

# ----------- MAIN PROCESSING ------------

def main():
    args = parse_arguments()
    setup_logging(args.log_file, args.verbose)

    # Print run information
    logging.info(f"Starting genre tagging script on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logging.info(f"Dry run: {args.dry_run}, Backup: {args.backup}")

    # Collect directories to process
    directories = [args.managed, args.unmanaged]
    if args.additional:
        directories.extend(args.additional)

    # Determine optimal number of workers
    available_cpus = cpu_count()
    num_workers = min(args.cpu_limit, available_cpus) if args.cpu_limit else available_cpus
    logging.info(f"Using {num_workers} out of {available_cpus} available CPU cores")

    # Collect all files to process with their base directory
    files_and_args = []
    for base_folder in directories:
        if not os.path.isdir(base_folder):
            logging.warning(f"Directory not found, skipping: {base_folder}")
            continue

        logging.info(f"Scanning {base_folder} ...")
        for fpath in find_audio_files(base_folder):
            files_and_args.append((fpath, base_folder, args.dry_run, args.backup, args.genre))

    if not files_and_args:
        logging.warning("No audio files found in the specified directories.")
        return

    logging.info(f"Total audio files found: {len(files_and_args)}")

    # Process files in batches
    process_files_in_batches(files_and_args, args.batch_size, num_workers)

    # Print summary
    if args.dry_run:
        logging.info("Dry run complete. No files were modified.")
    else:
        logging.info("Genre tagging complete.")

if __name__ == "__main__":
    main()
