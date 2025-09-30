"""Test platform detection in TranscriptionService."""

import sys
import os
import unittest
from unittest.mock import Mock, patch

# Add paths for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'lib', 'xml-stream'))


class TestPlatformDetection(unittest.TestCase):
    """Test that TranscriptionService selects correct keyboard injector."""

    def setUp(self):
        """Set up mock config."""
        self.config = Mock()
        self.config.use_xdotool = True
        self.config.debug_enabled = False
        self.config.xdotool_rate = 20  # Add numeric value for xdotool_rate

    @patch('sys.platform', 'darwin')
    @patch('transcription_service.MacOSKeyboardInjector')
    def test_macos_platform_detection(self, mock_macos_injector):
        """Test that macOS platform selects MacOSKeyboardInjector."""
        from transcription_service import TranscriptionService

        service = TranscriptionService(self.config)

        # Should instantiate MacOSKeyboardInjector regardless of use_xdotool setting
        mock_macos_injector.assert_called_once_with(self.config)

    @patch('sys.platform', 'linux')
    @patch('transcription_service.XdotoolKeyboardInjector')
    def test_linux_with_xdotool(self, mock_xdotool_injector):
        """Test that Linux with xdotool enabled selects XdotoolKeyboardInjector."""
        from transcription_service import TranscriptionService

        service = TranscriptionService(self.config)

        mock_xdotool_injector.assert_called_once_with(self.config)

    @patch('sys.platform', 'linux')
    @patch('transcription_service.MockKeyboardInjector')
    def test_linux_without_xdotool(self, mock_keyboard_injector):
        """Test that Linux without xdotool selects MockKeyboardInjector."""
        self.config.use_xdotool = False

        from transcription_service import TranscriptionService

        service = TranscriptionService(self.config)

        mock_keyboard_injector.assert_called_once()

    @patch('sys.platform', 'win32')
    @patch('transcription_service.XdotoolKeyboardInjector')
    def test_windows_platform_with_xdotool(self, mock_xdotool_injector):
        """Test that Windows platform with xdotool enabled selects XdotoolKeyboardInjector."""
        from transcription_service import TranscriptionService

        service = TranscriptionService(self.config)

        # Windows with use_xdotool=True should use XdotoolKeyboardInjector
        mock_xdotool_injector.assert_called_once_with(self.config)

    @patch('sys.platform', 'win32')
    @patch('transcription_service.MockKeyboardInjector')
    def test_windows_platform_without_xdotool(self, mock_keyboard_injector):
        """Test that Windows platform without xdotool selects MockKeyboardInjector."""
        self.config.use_xdotool = False

        from transcription_service import TranscriptionService

        service = TranscriptionService(self.config)

        # Windows with use_xdotool=False should use MockKeyboardInjector
        mock_keyboard_injector.assert_called_once()


if __name__ == '__main__':
    unittest.main()