"""Test import error handling for macOS keyboard injector."""

import sys
import os
import unittest
from unittest.mock import Mock, patch

# Add paths for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'lib', 'xml-stream'))


class TestImportErrorHandling(unittest.TestCase):
    """Test that import errors are handled gracefully."""

    def setUp(self):
        """Set up mock config."""
        self.config = Mock()
        self.config.debug_enabled = False
        self.config.xdotool_rate = 20

    @patch('sys.platform', 'darwin')
    def test_macos_injector_import_error(self):
        """Test that ImportError from MacOSKeyboardInjector falls back to MockKeyboardInjector."""
        with patch('transcription_service.MacOSKeyboardInjector') as mock_macos:
            mock_macos.side_effect = ImportError("PyObjC framework not available")

            from transcription_service import TranscriptionService
            service = TranscriptionService(self.config)

            from keyboard_injector import MockKeyboardInjector
            self.assertIsInstance(service.keyboard, MockKeyboardInjector)

    def test_successful_linux_instantiation(self):
        """Test that TranscriptionService uses XdotoolKeyboardInjector on Linux."""
        with patch('sys.platform', 'linux'):
            from transcription_service import TranscriptionService

            service = TranscriptionService(self.config)

            from lib.keyboard_injector_xdotool import XdotoolKeyboardInjector
            self.assertIsInstance(service.keyboard, XdotoolKeyboardInjector)

    @patch('sys.platform', 'linux')
    def test_xdotool_injector_on_linux(self):
        """Test that XdotoolKeyboardInjector works on Linux."""
        from transcription_service import TranscriptionService

        service = TranscriptionService(self.config)

        from lib.keyboard_injector_xdotool import XdotoolKeyboardInjector
        self.assertIsInstance(service.keyboard, XdotoolKeyboardInjector)


if __name__ == '__main__':
    unittest.main()