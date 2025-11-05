import os
import sys
import shutil
from pathlib import Path
from .colors import print_white, print_error

def check_ffmpeg():
    """Check if ffmpeg and ffprobe are available."""
    ffmpeg_path = shutil.which('ffmpeg')
    ffprobe_path = shutil.which('ffprobe')
    
    if not ffmpeg_path or not ffprobe_path:
        print_error("ffmpeg and ffprobe are required but not found")
        print_white("install ffmpeg:")
        print_white("  ubuntu/debian: sudo apt install ffmpeg")
        print_white("  macos: brew install ffmpeg") 
        print_white("  windows: download from https://ffmpeg.org/")
        return False
    return True

def get_default_download_dir():
    """Get default download directory."""
    # Try /downloads first, fall back to ./downloads
    try:
        download_dir = Path('/downloads')
        download_dir.mkdir(exist_ok=True)
        return download_dir
    except (PermissionError, OSError):
        download_dir = Path('./downloads')
        download_dir.mkdir(exist_ok=True)
        print_error("couldn't create /downloads, using ./downloads")
        return download_dir

def format_size(bytes):
    """Format bytes in human readable format."""
    for unit in ['b', 'kb', 'mb', 'gb']:
        if bytes < 1024.0:
            return f"{bytes:.1f}{unit}"
        bytes /= 1024.0
    return f"{bytes:.1f}tb"

def safe_filename(filename):
    """Make filename safe for filesystem."""
    # Replace problematic characters
    unsafe = '<>:"/\\|?*'
    for char in unsafe:
        filename = filename.replace(char, '_')
    return filename.strip(' .')