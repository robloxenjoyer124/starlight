#!/usr/bin/env python3
"""
EDL (Edit Decision List) Downloader
A configurable media downloader with customizable defaults for audio/video processing.
"""

import os
import sys
import json
import logging
import argparse
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any

try:
    import yt_dlp
except ImportError:
    print("Error: yt-dlp is required. Install with: pip install yt-dlp")
    sys.exit(1)

__version__ = "1.0.0"


@dataclass
class DownloadConfig:
    """Configuration for download settings."""
    output_folder: str = "~/Downloads/EDL"
    audio_format: str = "mp3"
    audio_quality: str = "320"
    video_format: str = "mkv"
    video_quality: str = "best"
    embed_artwork: bool = False
    prefer_mkv: bool = True
    download_playlist: bool = False
    max_concurrent_downloads: int = 3
    
    def __post_init__(self):
        """Expand user paths and validate settings."""
        self.output_folder = os.path.expanduser(self.output_folder)
        Path(self.output_folder).mkdir(parents=True, exist_ok=True)


class EDLDownloader:
    """Main downloader class with configurable defaults."""
    
    def __init__(self, config: Optional[DownloadConfig] = None):
        self.config = config or DownloadConfig()
        self.logger = self._setup_logging()
        self.ydl_opts = self._build_ydl_options()
    
    def _setup_logging(self) -> logging.Logger:
        """Configure logging for the downloader."""
        logger = logging.getLogger("EDLDownloader")
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        return logger
    
    def _build_ydl_options(self) -> Dict[str, Any]:
        """Build yt-dlp options based on configuration."""
        opts = {
            'quiet': False,
            'no_warnings': False,
            'extract_flat': False,
            'ignoreerrors': True,
            'restrictfilenames': True,
        }
        
        # Output template
        opts['outtmpl'] = os.path.join(
            self.config.output_folder,
            '%(title)s - %(uploader)s.%(ext)s'
        )
        
        # Format selection
        if self.config.prefer_mkv:
            opts['format'] = 'bestvideo[ext=mkv]+bestaudio/best[ext=mkv]/best'
        else:
            opts['format'] = 'best'
        
        # Audio post-processing
        postprocessors = []
        
        # Audio conversion
        if self.config.audio_format != 'original':
            audio_opts = {
                'key': 'FFmpegExtractAudio',
                'preferredcodec': self.config.audio_format,
                'preferredquality': self.config.audio_quality,
            }
            postprocessors.append(audio_opts)
        
        # Artwork embedding
        if self.config.embed_artwork:
            postprocessors.append({
                'key': 'EmbedThumbnail',
                'already_have_thumbnail': False,
            })
            opts['writethumbnail'] = True
        else:
            opts['writethumbnail'] = False
        
        opts['postprocessors'] = postprocessors
        
        # Playlist settings
        if not self.config.download_playlist:
            opts['noplaylist'] = True
        
        return opts
    
    def download(self, url: str) -> bool:
        """Download media from the given URL."""
        self.logger.info(f"Starting download from: {url}")
        self.logger.info(f"Output folder: {self.config.output_folder}")
        self.logger.info(f"Audio format: {self.config.audio_format} @ {self.config.audio_quality}kbps")
        self.logger.info(f"Video format: {self.config.video_format} (prefer MKV: {self.config.prefer_mkv})")
        self.logger.info(f"Embed artwork: {self.config.embed_artwork}")
        
        try:
            with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                ydl.download([url])
            self.logger.info("Download completed successfully!")
            return True
        except Exception as e:
            self.logger.error(f"Download failed: {e}")
            return False
    
    def download_multiple(self, urls: List[str]) -> Dict[str, bool]:
        """Download multiple URLs."""
        results = {}
        for url in urls:
            results[url] = self.download(url)
        return results
    
    def save_config(self, filepath: str) -> None:
        """Save current configuration to file."""
        config_path = Path(filepath)
        with open(config_path, 'w') as f:
            json.dump(asdict(self.config), f, indent=2)
        self.logger.info(f"Configuration saved to: {config_path}")
    
    def load_config(self, filepath: str) -> None:
        """Load configuration from file."""
        config_path = Path(filepath)
        if not config_path.exists():
            self.logger.warning(f"Config file not found: {config_path}")
            return
        
        with open(config_path, 'r') as f:
            config_data = json.load(f)
        
        self.config = DownloadConfig(**config_data)
        self.ydl_opts = self._build_ydl_options()
        self.logger.info(f"Configuration loaded from: {config_path}")


def display_banner():
    """Display the application banner."""
    banner = """
╔══════════════════════════════════════════════════════════════╗
║                    EDL Downloader v1.0.0                      ║
║              Edit Decision List Media Downloader              ║
║                                                                ║
║  Default Settings:                                             ║
║  • Audio: MP3 320kbps                                        ║
║  • Video: MKV (preferred)                                   ║
║  • Artwork: Disabled                                         ║
║  • Output: ~/Downloads/EDL                                   ║
╚══════════════════════════════════════════════════════════════╝
"""
    print(banner)


def get_login_credentials() -> Dict[str, str]:
    """Prompt user for login credentials if needed."""
    print("\n=== Login Configuration ===")
    print("Enter credentials for premium content (optional, press Enter to skip):")
    
    username = input("Username: ").strip()
    password = input("Password: ").strip()
    
    credentials = {}
    if username and password:
        credentials['username'] = username
        credentials['password'] = password
        print("Credentials saved for this session.")
    else:
        print("No credentials provided - continuing with free content access.")
    
    return credentials


def interactive_config_setup() -> DownloadConfig:
    """Interactive configuration setup."""
    print("\n=== Configuration Setup ===")
    print("Configure your EDL Downloader settings (press Enter for defaults):")
    
    config = DownloadConfig()
    
    # Output folder
    output = input(f"Output folder [{config.output_folder}]: ").strip()
    if output:
        config.output_folder = output
    
    # Audio format
    audio_format = input(f"Audio format [{config.audio_format}]: ").strip()
    if audio_format:
        config.audio_format = audio_format
    
    # Audio quality
    audio_quality = input(f"Audio quality (kbps) [{config.audio_quality}]: ").strip()
    if audio_quality:
        config.audio_quality = audio_quality
    
    # Video format preference
    prefer_mkv = input(f"Prefer MKV format [{config.prefer_mkv}] (y/n): ").strip().lower()
    if prefer_mkv in ('n', 'no', 'false'):
        config.prefer_mkv = False
    elif prefer_mkv in ('y', 'yes', 'true'):
        config.prefer_mkv = True
    
    # Artwork embedding
    embed_art = input(f"Embed artwork [{config.embed_artwork}] (y/n): ").strip().lower()
    if embed_art in ('y', 'yes', 'true'):
        config.embed_artwork = True
    elif embed_art in ('n', 'no', 'false'):
        config.embed_artwork = False
    
    return config


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="EDL Downloader - Configurable media downloader",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s https://youtube.com/watch?v=VIDEO_ID
  %(prog)s --config my_config.json --interactive
  %(prog)s --audio-format flac --audio-quality 0 URL1 URL2 URL3
        """
    )
    
    parser.add_argument('urls', nargs='*', help='URLs to download')
    parser.add_argument('--version', action='version', version=f'%(prog)s {__version__}')
    parser.add_argument('--interactive', '-i', action='store_true', 
                       help='Interactive configuration setup')
    parser.add_argument('--config', '-c', type=str, 
                       help='Load configuration from JSON file')
    parser.add_argument('--save-config', type=str, 
                       help='Save configuration to JSON file and exit')
    parser.add_argument('--output-folder', '-o', type=str,
                       help='Output folder for downloads')
    parser.add_argument('--audio-format', type=str, choices=['mp3', 'flac', 'wav', 'aac'],
                       help='Audio format')
    parser.add_argument('--audio-quality', type=str,
                       help='Audio quality (kbps for lossy, 0-10 for FLAC)')
    parser.add_argument('--prefer-mkv', action='store_true',
                       help='Prefer MKV format for videos')
    parser.add_argument('--no-mkv', dest='prefer_mkv', action='store_false',
                       help='Do not prefer MKV format')
    parser.add_argument('--embed-art', action='store_true',
                       help='Embed artwork in audio files')
    parser.add_argument('--no-art', dest='embed_artwork', action='store_false',
                       help='Do not embed artwork')
    parser.add_argument('--login', action='store_true',
                       help='Prompt for login credentials')
    
    args = parser.parse_args()
    
    display_banner()
    
    # Initialize configuration
    config = DownloadConfig()
    
    # Load config from file if specified
    if args.config:
        downloader = EDLDownloader(config)
        downloader.load_config(args.config)
        config = downloader.config
    else:
        downloader = EDLDownloader(config)
    
    # Override config with command line arguments
    if args.output_folder:
        config.output_folder = args.output_folder
    if args.audio_format:
        config.audio_format = args.audio_format
    if args.audio_quality:
        config.audio_quality = args.audio_quality
    
    # Only override boolean flags if they were explicitly provided
    import sys
    provided_args = sys.argv[1:]
    
    if '--prefer-mkv' in provided_args:
        config.prefer_mkv = True
    elif '--no-mkv' in provided_args:
        config.prefer_mkv = False
    
    if '--embed-art' in provided_args:
        config.embed_artwork = True
    elif '--no-art' in provided_args:
        config.embed_artwork = False
    
    # Interactive setup
    if args.interactive:
        config = interactive_config_setup()
        downloader.config = config
        downloader.ydl_opts = downloader._build_ydl_options()
    
    # Save config and exit if requested
    if args.save_config:
        downloader.save_config(args.save_config)
        return
    
    # Login credentials
    if args.login:
        credentials = get_login_credentials()
        if credentials:
            downloader.ydl_opts.update(credentials)
    
    # Validate URLs
    if not args.urls:
        print("\nNo URLs provided. Use --help for usage information.")
        if args.interactive:
            urls_input = input("\nEnter URLs to download (space separated): ").strip()
            if urls_input:
                args.urls = urls_input.split()
            else:
                return
        else:
            return
    
    # Perform downloads
    print(f"\nStarting downloads with {len(args.urls)} URL(s)...")
    results = downloader.download_multiple(args.urls)
    
    # Summary
    successful = sum(1 for success in results.values() if success)
    total = len(results)
    print(f"\nDownload Summary: {successful}/{total} completed successfully")
    
    for url, success in results.items():
        status = "✓" if success else "✗"
        print(f"{status} {url}")


if __name__ == "__main__":
    main()