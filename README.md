# EDL Downloader

A configurable media downloader with customizable defaults for audio/video processing. This tool supports downloading from various platforms including YouTube, SoundCloud, and other sites supported by yt-dlp.

## Features

- **Audio Processing**: Default to MP3 320kbps with support for FLAC, WAV, AAC
- **Video Processing**: Prefer MKV format with configurable quality settings
- **Artwork Control**: Disabled by default, can be enabled on demand
- **Configurable Output**: Custom output folder (default: `~/Downloads/EDL`)
- **Interactive Setup**: Guided configuration for first-time users
- **Login Support**: Optional credential handling for premium content
- **Batch Downloads**: Process multiple URLs simultaneously
- **Configuration Persistence**: Save and load settings from JSON files

## Default Configuration

The downloader comes with the following optimized defaults:

- **Audio Format**: MP3
- **Audio Quality**: 320kbps
- **Video Format**: MKV (preferred)
- **Artwork Embedding**: Disabled
- **Output Folder**: `~/Downloads/EDL`
- **Playlist Downloads**: Disabled (single items only)

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd edl-downloader
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Basic Usage

Download a single video:
```bash
python edl_downloader.py https://youtube.com/watch?v=VIDEO_ID
```

Download multiple URLs:
```bash
python edl_downloader.py URL1 URL2 URL3
```

### Interactive Configuration

Launch the interactive setup:
```bash
python edl_downloader.py --interactive
```

### Configuration Management

Save current settings:
```bash
python edl_downloader.py --save-config my_config.json
```

Load settings from file:
```bash
python edl_downloader.py --config my_config.json URL1 URL2
```

### Advanced Options

Custom audio format and quality:
```bash
python edl_downloader.py --audio-format flac --audio-quality 0 URL
```

Custom output folder:
```bash
python edl_downloader.py --output-folder /path/to/downloads URL
```

Enable artwork embedding:
```bash
python edl_downloader.py --embed-art URL
```

Use login credentials for premium content:
```bash
python edl_downloader.py --login URL
```

## Configuration Options

| Option | Default | Description |
|--------|---------|-------------|
| `output_folder` | `~/Downloads/EDL` | Directory for downloaded files |
| `audio_format` | `mp3` | Audio format (mp3, flac, wav, aac) |
| `audio_quality` | `320` | Audio quality in kbps (lossy) or 0-10 (FLAC) |
| `video_format` | `mkv` | Video container format |
| `prefer_mkv` | `True` | Prefer MKV over other formats |
| `embed_artwork` | `False` | Embed album art in audio files |
| `download_playlist` | `False` | Download entire playlists |
| `max_concurrent_downloads` | `3` | Maximum concurrent downloads |

## Examples

### High-Quality Audio Download
```bash
python edl_downloader.py --audio-format flac --audio-quality 0 --embed-art https://youtube.com/watch?v=VIDEO_ID
```

### Video Download with Custom Output
```bash
python edl_downloader.py --output-folder /media/Videos --prefer-mkv https://youtube.com/watch?v=VIDEO_ID
```

### Batch Download with Configuration
```bash
# Create config
python edl_downloader.py --save-config production.json --audio-format mp3 --audio-quality 320 --no-art

# Use config for batch downloads
python edl_downloader.py --config production.json URL1 URL2 URL3 URL4
```

## Login and Premium Content

For platforms requiring authentication, use the `--login` flag:

```bash
python edl_downloader.py --login https://example.com/premium-content
```

You'll be prompted to enter credentials securely. Credentials are only stored in memory for the current session.

## Configuration File Format

Configuration files use JSON format:

```json
{
  "output_folder": "/path/to/downloads",
  "audio_format": "mp3",
  "audio_quality": "320",
  "video_format": "mkv",
  "video_quality": "best",
  "embed_artwork": false,
  "prefer_mkv": true,
  "download_playlist": false,
  "max_concurrent_downloads": 3
}
```

## Supported Platforms

This downloader supports all platforms compatible with yt-dlp, including:

- YouTube
- SoundCloud
- Bandcamp
- Vimeo
- Twitch
- And many more...

## Requirements

- Python 3.6+
- yt-dlp
- FFmpeg (for audio/video processing)

## License

This project is licensed under the MIT License.