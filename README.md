# Audio Genre Tagger

A Python script to automatically update the genre metadata tags of audio files in a music library based on their folder structure. This tool traverses music directories and sets genre tags according to the parent folder name, making it ideal for organizing large music collections.

## Features

- **Multi-format Support**: Handles all major audio formats via Mutagen library (MP3, FLAC, MP4/M4A, OGG, WMA, and many more)
- **Parallel Processing**: Uses multiprocessing for efficient handling of large music libraries
- **Smart Skipping**: Only updates files that need changes, preserving existing correct tags
- **Flexible Configuration**: Command-line options for all major settings
- **Safety Features**: Dry-run mode and backup options
- **Progress Tracking**: Visual progress bars (when tqdm is available)
- **Comprehensive Logging**: Detailed logs with configurable verbosity
- **Genre Filtering**: Process only specific genres
- **Permission Handling**: Automatic permission fixes when possible

## Installation

### Debian/Ubuntu Systems

```bash
sudo apt update
sudo apt install python3-mutagen python3-tqdm
```

### Other Systems

```bash
# Using pip (may require virtual environment on some systems)
pip install mutagen tqdm

# Or with virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install mutagen tqdm
```

## Usage

### Basic Usage

```bash
# Run with default settings (dry-run recommended first)
python3 tag_genre_by_folder.py --dry-run

# Apply changes after reviewing dry-run output
python3 tag_genre_by_folder.py
```

### Common Options

```bash
# Process with backups and verbose logging
python3 tag_genre_by_folder.py --backup --verbose

# Process only Rock genres
python3 tag_genre_by_folder.py --genre "Rock"

# Custom music directory
python3 tag_genre_by_folder.py --music-base /mnt/music

# Limit CPU usage (useful for background processing)
python3 tag_genre_by_folder.py --cpu-limit 2

# Process additional directories
python3 tag_genre_by_folder.py --additional /mnt/external-music
```

## Command Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `--music-base PATH` | Base music directory | `/srv/dev-disk-by-uuid-c8158ed6-b7f4-4aab-9958-b0f3002b01aa/Media/Audio/Music/Sources` |
| `--managed PATH` | Managed music directory | `<music_base>/Managed` |
| `--unmanaged PATH` | Unmanaged music directory | `<music_base>/Unmanaged` |
| `--additional PATH` | Additional directories (can use multiple times) | None |
| `--cpu-limit N` | Limit CPU cores used | All available |
| `--dry-run` | Preview changes without modifying files | False |
| `--backup` | Create .bak files before changes | False |
| `--genre GENRE` | Only process matching genres | None |
| `--batch-size N` | Files processed per batch | 1000 |
| `--verbose` | Detailed logging output | False |
| `--log-file PATH` | Custom log file location | `genre_tagging.log` |
| `--no-progress` | Disable progress bar | False |

## Directory Structure

The script expects a specific folder structure where genre information is encoded in the directory name:

```
Music/
├── Managed/
│   ├── Rock - Classic/
│   │   ├── Led Zeppelin/
│   │   │   └── IV/
│   │   │       └── 01 - Black Dog.flac
│   │   └── Pink Floyd/
│   └── Electronic - Ambient/
│       └── Brian Eno/
└── Unmanaged/
    ├── Jazz - Fusion/
    └── Classical - Baroque/
```

In this example:

- `Rock - Classic` becomes the genre tag for all files in that directory tree
- `Electronic - Ambient` becomes the genre tag for Brian Eno files
- etc.

## Supported Audio Formats

| Format | Extensions | Notes |
|--------|------------|-------|
| MP3 | `.mp3`, `.mp2` | Uses ID3v2 tags |
| FLAC | `.flac` | Native Vorbis comments |
| MP4/AAC | `.mp4`, `.m4a`, `.m4b`, `.aac` | iTunes-style tags |
| OGG | `.ogg`, `.opus`, `.oga` | Vorbis comments |
| WMA | `.wma` | Windows Media format |
| Lossless | `.ape`, `.wv`, `.tta`, `.tak` | Various lossless formats |
| Other | `.aiff`, `.wav`, `.dsf`, `.dff` | Additional formats |

**Note**: Some formats (`.au`, `.acm`) are read-only and cannot be tagged.

## Genre Normalization

The script automatically normalizes genre names for consistency:

- Capitalizes words properly: `rock metal` → `Rock Metal`
- Preserves special terms: `r&b` → `R&B`, `edm` → `EDM`
- Handles hyphenated genres: `j-pop` → `J-Pop`
- Removes extra whitespace

## Examples

### Dry Run Example

```bash
python3 tag_genre_by_folder.py --dry-run --verbose
```

Output:
```
2025-09-02 09:12:48 [INFO] Starting genre tagging script on 2025-09-02 09:12:48
2025-09-02 09:12:48 [INFO] Dry run: True, Backup: False
2025-09-02 09:12:49 [INFO] Found 1250 audio files in /srv/.../Managed
2025-09-02 09:12:49 [INFO] Found 890 audio files in /srv/.../Unmanaged
2025-09-02 09:12:50 [INFO] Would update genre: track.flac - 'None' → 'Rock - Classic'
```

### Production Run with Backup

```bash
python3 tag_genre_by_folder.py --backup --cpu-limit 4
```

### Filter Specific Genre

```bash
python3 tag_genre_by_folder.py --genre "Electronic" --dry-run
```

## Logging

The script creates detailed logs in `genre_tagging.log` (configurable). Log levels include:

- **INFO**: Normal operations and file updates
- **WARNING**: Non-critical issues (unsupported formats, permission issues)
- **ERROR**: Critical errors that prevent processing
- **DEBUG**: Detailed information (visible with `--verbose`)

## Performance Considerations

- **Batch Processing**: Files are processed in batches (default 1000) to manage memory
- **CPU Usage**: Defaults to using all CPU cores; limit with `--cpu-limit`
- **I/O Optimization**: Only reads/writes files that need updates
- **Memory Efficient**: Processes files in batches rather than loading all into memory

## Safety Features

### Dry Run Mode

Always test with `--dry-run` first to preview changes:

```bash
python3 tag_genre_by_folder.py --dry-run --verbose
```

### Backup Option

Create backups before modifying files:

```bash
python3 tag_genre_by_folder.py --backup
```

### Permission Handling

The script attempts to fix permission issues automatically but logs when manual intervention is needed.

## Troubleshooting

### Common Issues

**"externally-managed-environment" error**

```bash
# Use system packages instead of pip
sudo apt install python3-mutagen python3-tqdm
```

**Permission denied errors**

```bash
# Run as user with appropriate permissions
# Or use sudo (not recommended for regular use)
sudo python3 tag_genre_by_folder.py
```

**No files found**

- Check that the music directory paths are correct
- Ensure audio files have supported extensions
- Verify directory permissions

### Verbose Logging

For detailed troubleshooting, use verbose mode:

```bash
python3 tag_genre_by_folder.py --verbose --dry-run
```

## Contributing

Feel free to submit issues and enhancement requests! When contributing:

1. Test thoroughly with `--dry-run` first
2. Include example directory structures in bug reports
3. Test with various audio formats
4. Update documentation for new features

## License

This script is provided as-is for personal and educational use. Please respect copyright laws when organizing your music collection.

## Version History

- **v2.0** (2025-09-02): Complete rewrite with improved error handling, command-line options, and batch processing
- **v1.0**: Initial version with basic functionality

---

**Last Updated**: 2025-09-02 by WB2024
