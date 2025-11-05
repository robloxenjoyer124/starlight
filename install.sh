#!/bin/bash

# EDL Downloader Installation Script

echo "Installing EDL Downloader..."

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is required but not installed."
    exit 1
fi

# Check if pip is installed
if ! command -v pip3 &> /dev/null && ! command -v pip &> /dev/null; then
    echo "Error: pip is required but not installed."
    exit 1
fi

# Install Python dependencies
echo "Installing Python dependencies..."
pip3 install -r requirements.txt

# Check if FFmpeg is installed
if ! command -v ffmpeg &> /dev/null; then
    echo ""
    echo "Warning: FFmpeg is not installed."
    echo "FFmpeg is required for audio/video processing."
    echo ""
    echo "Install FFmpeg:"
    echo "  Ubuntu/Debian: sudo apt install ffmpeg"
    echo "  macOS: brew install ffmpeg"
    echo "  Windows: Download from https://ffmpeg.org/download.html"
    echo ""
fi

# Create default output directory
mkdir -p ~/Downloads/EDL

# Make the main script executable
chmod +x edl_downloader.py

echo ""
echo "Installation complete!"
echo ""
echo "Usage:"
echo "  python3 edl_downloader.py --help"
echo "  python3 edl_downloader.py --interactive"
echo ""
echo "Default output directory: ~/Downloads/EDL"