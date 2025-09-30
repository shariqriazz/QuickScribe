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
        self.config.debug_enabled = False
        self.config.xdotool_rate = 20

    @patch('sys.platform', 'darwin')
    @patch('transcription_service.MacOSKeyboardInjector')
    def test_macos_platform_detection(self, mock_macos_injector):
        """Test that macOS platform selects MacOSKeyboardInjector."""
        from transcription_service import TranscriptionService

        service = TranscriptionService(self.config)

        mock_macos_injector.assert_called_once_with(self.config)

    @patch('sys.platform', 'linux')
    @patch('transcription_service.XdotoolKeyboardInjector')
    def test_linux_platform_detection(self, mock_xdotool_injector):
        """Test that Linux platform selects XdotoolKeyboardInjector."""
        from transcription_service import TranscriptionService

        service = TranscriptionService(self.config)

        mock_xdotool_injector.assert_called_once_with(self.config)

    @patch('sys.platform', 'freebsd13')
    @patch('transcription_service.XdotoolKeyboardInjector')
    def test_freebsd_platform_detection(self, mock_xdotool_injector):
        """Test that FreeBSD platform selects XdotoolKeyboardInjector."""
        from transcription_service import TranscriptionService

        service = TranscriptionService(self.config)

        mock_xdotool_injector.assert_called_once_with(self.config)

    @patch('sys.platform', 'win32')
    @patch('transcription_service.WindowsKeyboardInjector')
    def test_windows_platform_detection(self, mock_windows_injector):
        """Test that Windows platform selects WindowsKeyboardInjector."""
        from transcription_service import TranscriptionService

        service = TranscriptionService(self.config)

        mock_windows_injector.assert_called_once_with(self.config)

    @patch('sys.platform', 'unknown_os')
    @patch('transcription_service.MockKeyboardInjector')
    def test_unknown_platform_fallback(self, mock_keyboard_injector):
        """Test that unknown platform falls back to MockKeyboardInjector."""
        from transcription_service import TranscriptionService

        service = TranscriptionService(self.config)

        mock_keyboard_injector.assert_called_once()


if __name__ == '__main__':
    unittest.main()