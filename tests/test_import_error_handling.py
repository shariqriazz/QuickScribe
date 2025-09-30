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
        self.config.use_xdotool = False
        self.config.debug_enabled = False
        self.config.xdotool_rate = 20  # Add numeric value for xdotool_rate

    @patch('sys.platform', 'darwin')
    def test_macos_injector_import_error(self):
        """Test that ImportError from MacOSKeyboardInjector is handled."""
        # Mock the MacOSKeyboardInjector to raise ImportError
        with patch('transcription_service.MacOSKeyboardInjector') as mock_macos:
            mock_macos.side_effect = ImportError("PyObjC framework not available")

            # This should fail since macOS platform tries to use MacOSKeyboardInjector
            with self.assertRaises(ImportError):
                from transcription_service import TranscriptionService
                service = TranscriptionService(self.config)

    def test_successful_linux_instantiation(self):
        """Test that TranscriptionService works normally on Linux."""
        # Ensure we're not on macOS platform
        with patch('sys.platform', 'linux'):
            from transcription_service import TranscriptionService

            # Should succeed and use MockKeyboardInjector
            service = TranscriptionService(self.config)

            # Verify it's using MockKeyboardInjector
            from keyboard_injector import MockKeyboardInjector
            self.assertIsInstance(service.keyboard, MockKeyboardInjector)

    @patch('sys.platform', 'linux')
    def test_xdotool_injector_on_linux(self):
        """Test that XdotoolKeyboardInjector works on Linux."""
        self.config.use_xdotool = True

        from transcription_service import TranscriptionService

        # Should succeed and use XdotoolKeyboardInjector
        service = TranscriptionService(self.config)

        # Verify it's using XdotoolKeyboardInjector
        from lib.keyboard_injector_xdotool import XdotoolKeyboardInjector
        self.assertIsInstance(service.keyboard, XdotoolKeyboardInjector)


if __name__ == '__main__':
    unittest.main()