import os
import json
import keyring
from pathlib import Path
from .colors import print_white, print_error, print_success

SERVICE_NAME = "edl"

def get_config_dir():
    """Get platform-specific config directory."""
    if os.name == 'nt':  # Windows
        base_dir = os.environ.get('APPDATA', '')
        return Path(base_dir) / 'edl'
    elif os.name == 'posix':
        if os.uname().sysname == 'Darwin':  # macOS
            base_dir = os.path.expanduser('~/Library/Application Support')
        else:  # Linux/Unix
            base_dir = os.environ.get('XDG_CONFIG_HOME', os.path.expanduser('~/.config'))
        return Path(base_dir) / 'edl'
    else:
        # Fallback
        return Path(os.path.expanduser('~/.edl'))

def get_config_path():
    """Get path to config file."""
    config_dir = get_config_dir()
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / 'config.json'

def load_config():
    """Load config from file."""
    config_path = get_config_path()
    if config_path.exists():
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {}

def save_config(config):
    """Save config to file."""
    config_path = get_config_path()
    try:
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        return True
    except IOError:
        return False

def get_stored_username():
    """Get stored username from config."""
    config = load_config()
    return config.get('username')

def store_username(username):
    """Store username in config."""
    config = load_config()
    config['username'] = username
    return save_config(config)

def get_password(username):
    """Get password from keyring."""
    try:
        return keyring.get_password(SERVICE_NAME, username)
    except Exception:
        return None

def store_password(username, password):
    """Store password in keyring."""
    try:
        keyring.set_password(SERVICE_NAME, username, password)
        return True
    except Exception as e:
        print_error(f"warning: couldn't store password in keyring: {str(e)}")
        return False

def delete_password(username):
    """Delete password from keyring."""
    try:
        keyring.delete_password(SERVICE_NAME, username)
        return True
    except Exception:
        return False

def is_logged_in():
    """Check if user is logged in."""
    username = get_stored_username()
    if not username:
        return False
    password = get_password(username)
    return password is not None