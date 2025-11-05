#!/usr/bin/env python3
"""
Test script for EDL Downloader functionality
"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from edl_downloader import EDLDownloader, DownloadConfig


class TestDownloadConfig(unittest.TestCase):
    """Test configuration settings."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = DownloadConfig()
        self.assertEqual(config.audio_format, "mp3")
        self.assertEqual(config.audio_quality, "320")
        self.assertEqual(config.video_format, "mkv")
        self.assertTrue(config.prefer_mkv)
        self.assertFalse(config.embed_artwork)
        self.assertFalse(config.download_playlist)
    
    def test_config_path_expansion(self):
        """Test that user paths are expanded."""
        config = DownloadConfig(output_folder="~/test")
        expected = Path.home() / "test"
        self.assertEqual(config.output_folder, str(expected))


class TestEDLDownloader(unittest.TestCase):
    """Test EDL Downloader functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config = DownloadConfig(output_folder=self.temp_dir)
        self.downloader = EDLDownloader(self.config)
    
    def test_ydl_options_building(self):
        """Test yt-dlp options are built correctly."""
        opts = self.downloader._build_ydl_options()
        
        self.assertEqual(opts['format'], 'bestvideo[ext=mkv]+bestaudio/best[ext=mkv]/best')
        self.assertTrue(opts['noplaylist'])  # Should be True when download_playlist is False
        self.assertFalse(opts['writethumbnail'])
        
        # Check audio post-processor
        audio_pp = next((pp for pp in opts['postprocessors'] if pp['key'] == 'FFmpegExtractAudio'), None)
        self.assertIsNotNone(audio_pp)
        self.assertEqual(audio_pp['preferredcodec'], 'mp3')
        self.assertEqual(audio_pp['preferredquality'], '320')
    
    def test_config_save_load(self):
        """Test configuration saving and loading."""
        config_path = Path(self.temp_dir) / "test_config.json"
        
        # Save config
        self.downloader.save_config(str(config_path))
        self.assertTrue(config_path.exists())
        
        # Load config
        new_downloader = EDLDownloader()
        new_downloader.load_config(str(config_path))
        
        self.assertEqual(new_downloader.config.audio_format, self.config.audio_format)
        self.assertEqual(new_downloader.config.audio_quality, self.config.audio_quality)
    
    def test_artwork_embedding_options(self):
        """Test artwork embedding configuration."""
        # Test with artwork enabled
        config_with_art = DownloadConfig(embed_artwork=True)
        downloader_with_art = EDLDownloader(config_with_art)
        opts = downloader_with_art._build_ydl_options()
        
        self.assertTrue(opts['writethumbnail'])
        art_pp = next((pp for pp in opts['postprocessors'] if pp['key'] == 'EmbedThumbnail'), None)
        self.assertIsNotNone(art_pp)
        
        # Test with artwork disabled
        config_no_art = DownloadConfig(embed_artwork=False)
        downloader_no_art = EDLDownloader(config_no_art)
        opts = downloader_no_art._build_ydl_options()
        
        self.assertFalse(opts['writethumbnail'])
        art_pp = next((pp for pp in opts['postprocessors'] if pp['key'] == 'EmbedThumbnail'), None)
        self.assertIsNone(art_pp)


class TestBannerDisplay(unittest.TestCase):
    """Test banner display functionality."""
    
    @patch('builtins.print')
    def test_banner_display(self, mock_print):
        """Test that banner is displayed correctly."""
        from edl_downloader import display_banner
        display_banner()
        mock_print.assert_called()
        
        # Check that key information is in the banner
        call_args = str(mock_print.call_args)
        self.assertIn("EDL Downloader", call_args)
        self.assertIn("MP3 320kbps", call_args)
        self.assertIn("MKV", call_args)
        self.assertIn("Artwork: Disabled", call_args)


if __name__ == "__main__":
    unittest.main()