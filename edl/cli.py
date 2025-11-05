import argparse
import getpass
import sys
from .colors import print_banner, print_white, print_error, print_success
from .auth import (
    get_stored_username, store_username, get_password, store_password,
    is_logged_in
)
from .download import download_video
from .utils import get_default_download_dir

def create_parser():
    """Create argument parser."""
    parser = argparse.ArgumentParser(
        prog='edl',
        description='edgy youtube downloader with login, 4k, mp3+art, lossless'
    )
    
    subparsers = parser.add_subparsers(dest='command', help='available commands')
    
    # Login command
    login_parser = subparsers.add_parser('login', help='login to store credentials')
    
    # Download command
    download_parser = subparsers.add_parser('download', help='download video or audio')
    download_parser.add_argument('url', help='video or playlist url')
    download_parser.add_argument('--playlist', action='store_true', help='download full playlist')
    download_parser.add_argument('--audio', choices=['mp3', 'm4a', 'opus', 'flac', 'wav'], help='audio-only mode')
    download_parser.add_argument('--embed-art', action='store_true', default=True, help='embed album art (default true for audio)')
    download_parser.add_argument('--max-quality', type=int, choices=[2160, 1440, 1080, 720, 480, 360], default=2160, help='maximum video quality (default 2160)')
    download_parser.add_argument('--out', default=str(get_default_download_dir()), help='output directory (default /downloads)')
    download_parser.add_argument('--filename-template', default='%(title)s [%(id)s].%(ext)s', help='filename template')
    download_parser.add_argument('--cookies', help='cookies file path')
    
    return parser

def handle_login():
    """Handle login command."""
    print_white("enter your credentials:")
    
    try:
        username = input("username: ").strip()
        if not username:
            print_error("username cannot be empty")
            return False
        
        password = getpass.getpass("password: ")
        if not password:
            print_error("password cannot be empty")
            return False
        
        # Store credentials
        username_stored = store_username(username)
        password_stored = store_password(username, password)
        
        if username_stored and password_stored:
            print_success(f"logged in as {username}")
            return True
        else:
            print_error("failed to store credentials")
            return False
            
    except KeyboardInterrupt:
        print_error("\nlogin cancelled")
        return False
    except Exception as e:
        print_error(f"login failed: {str(e)}")
        return False

def handle_download(args):
    """Handle download command."""
    # Check if login is required for this URL (some videos require authentication)
    username = get_stored_username()
    password = None
    if username:
        password = get_password(username)
    
    # Add auth to args if available
    if username and password:
        args.username = username
        args.password = password
    
    # Set embed_art default for audio mode
    if args.audio and not hasattr(args, 'embed_art'):
        args.embed_art = True
    
    return download_video(args.url, args)

def show_greeting():
    """Show greeting based on login status."""
    if is_logged_in():
        username = get_stored_username()
        print_white(f"hey {username}")
    else:
        print_white("not logged in. run 'edl login' to authenticate")

def main():
    """Main entry point."""
    # Print banner
    print_banner()
    
    # Create parser
    parser = create_parser()
    
    # If no arguments, show greeting and help
    if len(sys.argv) == 1:
        show_greeting()
        parser.print_help()
        return 0
    
    # Parse arguments
    args = parser.parse_args()
    
    # Handle commands
    if args.command == 'login':
        success = handle_login()
        return 0 if success else 1
    
    elif args.command == 'download':
        success = handle_download(args)
        return 0 if success else 1
    
    else:
        parser.print_help()
        return 1

if __name__ == '__main__':
    sys.exit(main())