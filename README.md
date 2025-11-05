# edl

edgy youtube downloader with login, 4k, mp3+art, lossless

## installation

```bash
pip install edl
```

## requirements

- python 3.10+
- ffmpeg/ffprobe (required for audio conversion and embedding album art)
  - install via package manager:
    - ubuntu/debian: `sudo apt install ffmpeg`
    - macos: `brew install ffmpeg`
    - windows: download from https://ffmpeg.org/

## usage

```bash
# login (stores credentials securely)
edl login

# download video (4k when available)
edl download https://youtube.com/watch?v=example

# download audio as mp3 with embedded album art
edl download https://youtube.com/watch?v=example --audio mp3

# download playlist
edl download https://youtube.com/playlist?list=example --playlist

# download lossless audio
edl download https://youtube.com/watch?v=example --audio flac

# specify output directory
edl download https://youtube.com/watch?v=example --out ~/videos
```

## features

- secure credential storage using os keyring
- 4k video support
- audio extraction with embedded album art
- playlist downloads
- cross-platform config management
- edgy lowercase terminal style