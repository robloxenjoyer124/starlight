import pytest
from unittest.mock import patch, MagicMock
from edl.download import build_ydl_options, DownloadProgress

class TestFormatSelection:
    """Test format selection logic."""
    
    def test_video_format_selection(self):
        """Test video format selection with max quality."""
        # Mock args for video download
        args = MagicMock()
        args.out = './test_downloads'
        args.filename_template = '%(title)s [%(id)s].%(ext)s'
        args.playlist = False
        args.audio = None
        args.max_quality = 2160
        args.cookies = None
        
        with patch('pathlib.Path.mkdir'):
            options = build_ydl_options(args)
        
        assert options is not None
        assert 'format' in options
        assert 'bestvideo[height<=2160]+bestaudio/best[height<=2160]/best[height<=2160]' in options['format']
    
    def test_audio_format_selection(self):
        """Test audio format selection."""
        args = MagicMock()
        args.out = './test_downloads'
        args.filename_template = '%(title)s [%(id)s].%(ext)s'
        args.playlist = False
        args.audio = 'mp3'
        args.embed_art = True
        args.cookies = None
        
        with patch('edl.download.check_ffmpeg', return_value=True), \
             patch('pathlib.Path.mkdir'):
            options = build_ydl_options(args)
            
            assert options is not None
            assert options['format'] == 'bestaudio/best'
            assert 'postprocessors' in options
            
            # Check for audio extraction postprocessor
            audio_pp = next((pp for pp in options['postprocessors'] if pp['key'] == 'FFmpegExtractAudio'), None)
            assert audio_pp is not None
            assert audio_pp['preferredcodec'] == 'mp3'
            
            # Check for thumbnail embedding
            embed_pp = next((pp for pp in options['postprocessors'] if pp['key'] == 'EmbedThumbnail'), None)
            assert embed_pp is not None
            assert options['writethumbnail'] is True
    
    def test_audio_without_embed_art(self):
        """Test audio format selection without embedding art."""
        args = MagicMock()
        args.out = './test_downloads'
        args.filename_template = '%(title)s [%(id)s].%(ext)s'
        args.playlist = False
        args.audio = 'flac'
        args.embed_art = False
        args.cookies = None
        
        with patch('edl.download.check_ffmpeg', return_value=True), \
             patch('pathlib.Path.mkdir'):
            options = build_ydl_options(args)
            
            assert options is not None
            assert 'postprocessors' in options
            
            # Check for audio extraction
            audio_pp = next((pp for pp in options['postprocessors'] if pp['key'] == 'FFmpegExtractAudio'), None)
            assert audio_pp is not None
            assert audio_pp['preferredcodec'] == 'flac'
            
            # Should not have thumbnail embedding
            embed_pp = next((pp for pp in options['postprocessors'] if pp['key'] == 'EmbedThumbnail'), None)
            assert embed_pp is None
            assert options.get('writethumbnail') is not True
    
    def test_different_max_qualities(self):
        """Test different max quality settings."""
        qualities = [1440, 1080, 720, 480, 360]
        
        for quality in qualities:
            args = MagicMock()
            args.out = './test_downloads'
            args.filename_template = '%(title)s [%(id)s].%(ext)s'
            args.playlist = False
            args.audio = None
            args.max_quality = quality
            args.cookies = None
            
            with patch('pathlib.Path.mkdir'):
                options = build_ydl_options(args)
                
                assert options is not None
                assert f'height<={quality}' in options['format']
    
    def test_playlist_template(self):
        """Test playlist filename template."""
        args = MagicMock()
        args.out = './test_downloads'
        args.filename_template = 'playlist/%(playlist_index)s - %(title)s.%(ext)s'
        args.playlist = True
        args.audio = None
        args.max_quality = 1080
        args.cookies = None
        
        with patch('pathlib.Path.mkdir'):
            options = build_ydl_options(args)
            
            assert options is not None
            assert 'playlist' in options['outtmpl']
            assert 'playlist_index' in options['outtmpl']

class TestDownloadProgress:
    """Test download progress handling."""
    
    def test_progress_hook_downloading(self):
        """Test progress hook during download."""
        progress = DownloadProgress()
        
        # Mock download data
        d = {
            'status': 'downloading',
            'total_bytes': 1000000,
            'downloaded_bytes': 500000,
            'speed': 1000000,
            'eta': 30
        }
        
        # This should not raise an exception
        progress.hook(d)
    
    def test_progress_hook_finished(self):
        """Test progress hook when finished."""
        progress = DownloadProgress()
        
        d = {
            'status': 'finished',
            'filename': 'test.mp4'
        }
        
        # This should not raise an exception
        progress.hook(d)
    
    def test_progress_hook_error(self):
        """Test progress hook on error."""
        progress = DownloadProgress()
        
        d = {
            'status': 'error',
            'filename': 'test.mp4'
        }
        
        # This should not raise an exception
        progress.hook(d)