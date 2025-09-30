"""Tests for MacOSKeyboardInjector."""

import sys
import os
import unittest
from unittest.mock import Mock, patch, MagicMock

# Add the lib directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'lib'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'lib', 'xml-stream'))


class TestMacOSKeyboardInjector(unittest.TestCase):
    """Test MacOSKeyboardInjector behavior with mocked PyObjC."""

    def setUp(self):
        """Set up test environment with mocked PyObjC."""
        # Mock the PyObjC imports before importing MacOSKeyboardInjector
        self.mock_cgevent_create = Mock(return_value='mock_event')
        self.mock_cgevent_set_unicode = Mock()
        self.mock_cgevent_post = Mock(return_value=0)  # Return 0 for success
        self.mock_kg_hid_event_tap = 'mock_tap'

        # Create mock modules
        mock_quartz = MagicMock()
        mock_quartz.CoreGraphics.CGEventCreateKeyboardEvent = self.mock_cgevent_create
        mock_quartz.CoreGraphics.CGEventKeyboardSetUnicodeString = self.mock_cgevent_set_unicode
        mock_quartz.CoreGraphics.CGEventPost = self.mock_cgevent_post
        mock_quartz.CoreGraphics.kCGHIDEventTap = self.mock_kg_hid_event_tap

        mock_app_services = MagicMock()
        mock_app_services.AXIsProcessTrusted = Mock(return_value=True)

        # Patch the imports
        with patch.dict('sys.modules', {
            'Quartz': mock_quartz,
            'Quartz.CoreGraphics': mock_quartz.CoreGraphics,
            'ApplicationServices': mock_app_services
        }):
            from keyboard_injector_macos import MacOSKeyboardInjector
            self.MacOSKeyboardInjector = MacOSKeyboardInjector

    def test_init_without_config(self):
        """Test initialization without config."""
        injector = self.MacOSKeyboardInjector()
        self.assertEqual(injector.typing_delay, 5)
        self.assertFalse(injector.debug_enabled)

    def test_init_with_config(self):
        """Test initialization with config."""
        config = Mock()
        config.xdotool_rate = 20  # 20 Hz
        config.debug_enabled = True

        injector = self.MacOSKeyboardInjector(config)
        self.assertEqual(injector.typing_delay, 50)  # 1000/20 = 50ms
        self.assertTrue(injector.debug_enabled)

    @patch.dict(os.environ, {'TESTING': 'true'})
    def test_test_mode_detection(self):
        """Test that test mode is detected correctly."""
        injector = self.MacOSKeyboardInjector()
        self.assertTrue(injector.test_mode)

    def test_bksp_in_test_mode(self):
        """Test that backspace does nothing in test mode."""
        with patch.dict(os.environ, {'TESTING': 'true'}):
            injector = self.MacOSKeyboardInjector()
            injector.bksp(5)

        # Should not call any CGEvent functions
        self.mock_cgevent_create.assert_not_called()
        self.mock_cgevent_post.assert_not_called()

    def test_emit_in_test_mode(self):
        """Test that emit does nothing in test mode."""
        with patch.dict(os.environ, {'TESTING': 'true'}):
            injector = self.MacOSKeyboardInjector()
            injector.emit("test text")

        # Should not call any CGEvent functions
        self.mock_cgevent_create.assert_not_called()
        self.mock_cgevent_post.assert_not_called()

    @patch('time.sleep')
    def test_bksp_normal_mode(self, mock_sleep):
        """Test backspace in normal mode."""
        with patch.dict(os.environ, {}, clear=True):
            injector = self.MacOSKeyboardInjector()
            injector.test_mode = False  # Force normal mode
            injector.bksp(2)

        # Should create 4 events (2 key down + 2 key up)
        self.assertEqual(self.mock_cgevent_create.call_count, 4)

        # Check key down calls (True parameter)
        key_down_calls = [call for call in self.mock_cgevent_create.call_args_list if call[0][2] is True]
        self.assertEqual(len(key_down_calls), 2)

        # Check key up calls (False parameter)
        key_up_calls = [call for call in self.mock_cgevent_create.call_args_list if call[0][2] is False]
        self.assertEqual(len(key_up_calls), 2)

        # Should post 4 events
        self.assertEqual(self.mock_cgevent_post.call_count, 4)

    @patch('time.sleep')
    def test_emit_single_line(self, mock_sleep):
        """Test emit with single line text."""
        with patch.dict(os.environ, {}, clear=True):
            injector = self.MacOSKeyboardInjector()
            injector.test_mode = False  # Force normal mode
            injector.emit("hello")

        # Should create 1 event and set Unicode string
        self.mock_cgevent_create.assert_called_once_with(None, 0, True)
        self.mock_cgevent_set_unicode.assert_called_once()
        self.mock_cgevent_post.assert_called_once()

    @patch('time.sleep')
    def test_emit_multiline(self, mock_sleep):
        """Test emit with multiline text."""
        with patch.dict(os.environ, {}, clear=True):
            injector = self.MacOSKeyboardInjector()
            injector.test_mode = False  # Force normal mode
            injector.emit("line1\nline2")

        # Should create events for text + return keys
        # 2 text events + 2 return events (down+up)
        self.assertEqual(self.mock_cgevent_create.call_count, 4)
        self.assertEqual(self.mock_cgevent_post.call_count, 4)

    def test_empty_text_emit(self):
        """Test emit with empty text."""
        injector = self.MacOSKeyboardInjector()
        injector.test_mode = False  # Force normal mode
        injector.emit("")

        # Should not call any CGEvent functions for empty text
        self.mock_cgevent_create.assert_not_called()
        self.mock_cgevent_post.assert_not_called()

    def test_zero_count_bksp(self):
        """Test backspace with zero count."""
        injector = self.MacOSKeyboardInjector()
        injector.test_mode = False  # Force normal mode
        injector.bksp(0)

        # Should not call any CGEvent functions for zero count
        self.mock_cgevent_create.assert_not_called()
        self.mock_cgevent_post.assert_not_called()

    def test_permission_check_prevents_injection(self):
        """Test that missing permissions prevents keyboard injection."""
        injector = self.MacOSKeyboardInjector()
        injector.test_mode = False  # Force normal mode

        # Mock AXIsProcessTrusted to return False (no permissions)
        with patch.object(injector, '_check_accessibility_permissions', return_value=False):
            with patch.object(injector, '_show_permission_instructions') as mock_show_instructions:
                injector.bksp(1)
                injector.emit("test")

                # Should show instructions twice (once for each method call)
                self.assertEqual(mock_show_instructions.call_count, 2)

                # Should not call any CGEvent functions
                self.mock_cgevent_create.assert_not_called()
                self.mock_cgevent_post.assert_not_called()

    def test_permission_warning_shown_once(self):
        """Test that permission warning is only shown once to avoid spam."""
        injector = self.MacOSKeyboardInjector()
        injector.test_mode = False  # Force normal mode

        # Mock AXIsProcessTrusted to return False (no permissions)
        with patch.object(injector, '_check_accessibility_permissions', return_value=False):
            with patch('builtins.print') as mock_print:
                # Call multiple times
                injector._show_permission_instructions()
                injector._show_permission_instructions()
                injector._show_permission_instructions()

                # Should only print the first time
                # Count calls that contain the permission message
                permission_calls = [call for call in mock_print.call_args_list
                                  if 'ACCESSIBILITY PERMISSION REQUIRED' in str(call)]
                self.assertEqual(len(permission_calls), 1)


if __name__ == '__main__':
    unittest.main()