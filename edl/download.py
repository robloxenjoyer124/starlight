import yt_dlp
from pathlib import Path
from .colors import print_white, print_error, print_success
from .utils import check_ffmpeg

class DownloadProgress:
    """Progress handler for yt-dlp downloads."""
    
    def __init__(self):
        self.current = 0
        self.total = 0
    
    def hook(self, d):
        """Progress hook function."""
        if d['status'] == 'downloading':
            self._show_progress(d)
        elif d['status'] == 'finished':
            print_white(f"finished downloading: {d.get('filename', 'unknown')}")
        elif d['status'] == 'error':
            print_error(f"download failed: {d.get('filename', 'unknown')}")
    
    def _show_progress(self, d):
        """Show download progress."""
        total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
        downloaded_bytes = d.get('downloaded_bytes', 0)
        
        if total_bytes > 0:
            percent = (downloaded_bytes / total_bytes) * 100
            speed = d.get('speed', 0)
            eta = d.get('eta', 0)
            
            # Format speed
            if speed:
                if speed < 1024:
                    speed_str = f"{speed:.1f}b/s"
                elif speed < 1024 * 1024:
                    speed_str = f"{speed/1024:.1f}kb/s"
                else:
                    speed_str = f"{speed/(1024*1024):.1f}mb/s"
            else:
                speed_str = "n/a"
            
            # Format ETA
            if eta and eta > 0:
                if eta < 60:
                    eta_str = f"{eta}s"
                elif eta < 3600:
                    eta_str = f"{eta//60}m{eta%60}s"
                else:
                    eta_str = f"{eta//3600}h{(eta%3600)//60}m"
            else:
                eta_str = "n/a"
            
            # Progress bar
            bar_length = 30
            filled_length = int(bar_length * percent / 100)
            bar = '█' * filled_length + '░' * (bar_length - filled_length)
            
            print(f"\r{bar} {percent:.1f}% {speed_str} eta: {eta_str}", end='', flush=True)

def build_ydl_options(args):
    """Build yt-dlp options from command line args."""
    
    # Basic options
    ydl_opts = {
        'progress_hooks': [DownloadProgress().hook],
        'quiet': True,
        'no_warnings': True,
    }
    
    # Output directory and template
    out_dir = Path(args.out).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    
    if hasattr(args, 'playlist') and args.playlist:
        ydl_opts['outtmpl'] = str(out_dir / args.filename_template)
    else:
        ydl_opts['outtmpl'] = str(out_dir / args.filename_template)
    
    # Cookies file
    if args.cookies:
        ydl_opts['cookiefile'] = args.cookies
    
    # Audio mode
    if args.audio:
        if not check_ffmpeg():
            return None
        
        # Audio format options
        postprocessors = []
        
        # Extract audio
        postprocessors.append({
            'key': 'FFmpegExtractAudio',
            'preferredcodec': args.audio,
            'preferredquality': '0',  # Best quality
        })
        
        # Embed thumbnail (album art)
        if args.embed_art:
            postprocessors.append({
                'key': 'EmbedThumbnail',
            })
            postprocessors.append({
                'key': 'FFmpegMetadata',
            })
            # Also download thumbnail
            ydl_opts['writethumbnail'] = True
        
        ydl_opts['postprocessors'] = postprocessors
        
        # Format selection for audio
        ydl_opts['format'] = 'bestaudio/best'
        
    else:
        # Video mode
        max_quality = args.max_quality
        ydl_opts['format'] = f'bestvideo[height<={max_quality}]+bestaudio/best[height<={max_quality}]/best[height<={max_quality}]'
    
    return ydl_opts

def download_video(url, args):
    """Download video using yt-dlp."""
    ydl_opts = build_ydl_options(args)
    if ydl_opts is None:
        return False
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Extract info first to check if it's a playlist
            info = ydl.extract_info(url, download=False)
            
            if not hasattr(args, 'playlist') or not args.playlist:
                if info.get('_type') == 'playlist':
                    print_error("this is a playlist. use --playlist to download all items")
                    return False
            
            print_white(f"starting download: {info.get('title', 'unknown')}")
            ydl.download([url])
            print_success("download completed successfully")
            return True
            
    except Exception as e:
        print_error(f"download failed: {str(e)}")
        return False