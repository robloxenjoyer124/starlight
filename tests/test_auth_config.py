import pytest
from unittest.mock import patch, MagicMock, mock_open
import json
import tempfile
import os
from pathlib import Path

class TestAuthConfig:
    """Test authentication and configuration handling."""
    
    def test_get_config_dir_linux(self):
        """Test config directory on Linux."""
        with patch('os.name', 'posix'), \
             patch('os.uname') as mock_uname, \
             patch('os.environ', {'XDG_CONFIG_HOME': '/home/user/.config'}):
            
            mock_uname.return_value.sysname = 'Linux'
            
            from edl.auth import get_config_dir
            config_dir = get_config_dir()
            
            assert str(config_dir) == '/home/user/.config/edl'
    
    def test_get_config_dir_macos(self):
        """Test config directory on macOS."""
        with patch('os.name', 'posix'), \
             patch('os.uname') as mock_uname, \
             patch('os.path.expanduser') as mock_expand:
            
            mock_uname.return_value.sysname = 'Darwin'
            mock_expand.return_value = '/Users/testuser'
            
            from edl.auth import get_config_dir
            config_dir = get_config_dir()
            
            # Check that it contains the expected components
            config_str = str(config_dir)
            assert 'testuser' in config_str
            assert 'edl' in config_str
    
    @pytest.mark.skip(reason="Windows-specific test cannot run on Unix system")
    def test_get_config_dir_windows(self):
        """Test config directory on Windows."""
        with patch('os.name', 'nt'), \
             patch('os.environ', {'APPDATA': 'C:\\Users\\test\\AppData\\Roaming'}):
            
            from edl.auth import get_config_dir
            config_dir = get_config_dir()
            
            # Convert path separators for comparison
            assert 'edl' in str(config_dir)
            assert 'AppData' in str(config_dir)
            assert 'Roaming' in str(config_dir)
    
    def test_load_config_empty(self):
        """Test loading config when file doesn't exist."""
        mock_path = MagicMock()
        mock_path.exists.return_value = False
        
        with patch('edl.auth.get_config_path', return_value=mock_path):
            from edl.auth import load_config
            config = load_config()
            
            assert config == {}
    
    def test_load_config_valid(self):
        """Test loading valid config file."""
        test_config = {'username': 'testuser', 'setting': 'value'}
        
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        
        with patch('builtins.open', mock_open(read_data=json.dumps(test_config))), \
             patch('edl.auth.get_config_path', return_value=mock_path):
            
            from edl.auth import load_config
            config = load_config()
            
            assert config == test_config
    
    def test_load_config_invalid_json(self):
        """Test loading config with invalid JSON."""
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        
        with patch('builtins.open', mock_open(read_data='invalid json')), \
             patch('edl.auth.get_config_path', return_value=mock_path):
            
            from edl.auth import load_config
            config = load_config()
            
            assert config == {}
    
    def test_save_config_success(self):
        """Test saving config successfully."""
        test_config = {'username': 'testuser'}
        
        with patch('builtins.open', mock_open()) as mock_file, \
             patch('edl.auth.get_config_path') as mock_path:
            
            from edl.auth import save_config
            result = save_config(test_config)
            
            assert result is True
            mock_file.assert_called_once()
    
    def test_save_config_failure(self):
        """Test saving config with IOError."""
        with patch('builtins.open', side_effect=IOError('Permission denied')):
            from edl.auth import save_config
            result = save_config({'username': 'testuser'})
            
            assert result is False
    
    @patch('edl.auth.load_config')
    @patch('edl.auth.save_config')
    def test_get_stored_username(self, mock_save, mock_load):
        """Test getting stored username."""
        mock_load.return_value = {'username': 'testuser'}
        
        from edl.auth import get_stored_username
        username = get_stored_username()
        
        assert username == 'testuser'
    
    @patch('edl.auth.save_config')
    @patch('edl.auth.load_config')
    def test_store_username(self, mock_load, mock_save):
        """Test storing username."""
        mock_load.return_value = {}
        mock_save.return_value = True
        
        from edl.auth import store_username
        result = store_username('testuser')
        
        assert result is True
        mock_save.assert_called_once_with({'username': 'testuser'})
    
    @patch('keyring.get_password')
    def test_get_password(self, mock_get):
        """Test getting password from keyring."""
        mock_get.return_value = 'testpass'
        
        from edl.auth import get_password
        password = get_password('testuser')
        
        assert password == 'testpass'
        mock_get.assert_called_once_with('edl', 'testuser')
    
    @patch('keyring.set_password')
    def test_store_password(self, mock_set):
        """Test storing password in keyring."""
        mock_set.return_value = None
        
        from edl.auth import store_password
        result = store_password('testuser', 'testpass')
        
        assert result is True
        mock_set.assert_called_once_with('edl', 'testuser', 'testpass')
    
    @patch('keyring.set_password')
    def test_store_password_failure(self, mock_set):
        """Test storing password with keyring failure."""
        mock_set.side_effect = Exception('Keyring error')
        
        from edl.auth import store_password
        result = store_password('testuser', 'testpass')
        
        assert result is False
    
    @patch('edl.auth.get_password')
    @patch('edl.auth.get_stored_username')
    def test_is_logged_in_true(self, mock_username, mock_password):
        """Test is_logged_in returns True when credentials exist."""
        mock_username.return_value = 'testuser'
        mock_password.return_value = 'testpass'
        
        from edl.auth import is_logged_in
        result = is_logged_in()
        
        assert result is True
    
    @patch('edl.auth.get_password')
    @patch('edl.auth.get_stored_username')
    def test_is_logged_in_false_no_username(self, mock_username, mock_password):
        """Test is_logged_in returns False when no username."""
        mock_username.return_value = None
        
        from edl.auth import is_logged_in
        result = is_logged_in()
        
        assert result is False
    
    @patch('edl.auth.get_password')
    @patch('edl.auth.get_stored_username')
    def test_is_logged_in_false_no_password(self, mock_username, mock_password):
        """Test is_logged_in returns False when no password."""
        mock_username.return_value = 'testuser'
        mock_password.return_value = None
        
        from edl.auth import is_logged_in
        result = is_logged_in()
        
        assert result is False