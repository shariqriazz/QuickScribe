"""Tests for WindowsKeyboardInjector."""

import unittest
import sys
import os
from unittest.mock import patch, MagicMock, call

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))


class TestWindowsKeyboardInjector(unittest.TestCase):
    """Test WindowsKeyboardInjector behavior with mocked ctypes."""

    def setUp(self):
        """Mock the ctypes imports before importing WindowsKeyboardInjector."""
        self.mock_ctypes = MagicMock()
        self.mock_wintypes = MagicMock()
        self.mock_user32 = MagicMock()
        self.mock_user32.SendInput.return_value = 1

        self.ctypes_patcher = patch.dict('sys.modules', {
            'ctypes': self.mock_ctypes,
            'ctypes.wintypes': self.mock_wintypes
        })
        self.ctypes_patcher.start()

        self.mock_ctypes.WinDLL.return_value = self.mock_user32
        self.mock_ctypes.pointer.return_value = MagicMock()
        self.mock_ctypes.byref.return_value = MagicMock()
        self.mock_ctypes.sizeof.return_value = 40

        with patch('keyboard_injector_windows.CTYPES_AVAILABLE', True):
            from keyboard_injector_windows import WindowsKeyboardInjector
            self.WindowsKeyboardInjector = WindowsKeyboardInjector

    def tearDown(self):
        """Stop the ctypes patcher."""
        self.ctypes_patcher.stop()

    def test_initialization(self):
        """Test basic initialization."""
        injector = self.WindowsKeyboardInjector()
        self.assertEqual(injector.typing_delay, 5)
        self.assertFalse(injector.debug_enabled)

    def test_initialization_with_config(self):
        """Test initialization with config."""
        config = MagicMock()
        config.xdotool_rate = 100
        config.debug_enabled = False
        injector = self.WindowsKeyboardInjector(config)
        self.assertEqual(injector.typing_delay, 10)

    def test_bksp_basic(self):
        """Test backspace basic functionality."""
        with patch.dict(os.environ, {'TESTING': 'false', 'PYTEST_CURRENT_TEST': '', '_': ''}, clear=True):
            with patch('sys.argv', ['test']):
                injector = self.WindowsKeyboardInjector()
                self.assertFalse(injector.test_mode)
                with patch.object(injector, '_send_key') as mock_send:
                    injector.bksp(1)
                    self.assertEqual(mock_send.call_count, 2)

    def test_bksp_zero_count(self):
        """Test backspace with zero count."""
        injector = self.WindowsKeyboardInjector()
        with patch.object(injector, '_send_key') as mock_send:
            injector.bksp(0)
            mock_send.assert_not_called()

    def test_emit_basic(self):
        """Test emit basic functionality."""
        with patch.dict(os.environ, {'TESTING': 'false', 'PYTEST_CURRENT_TEST': '', '_': ''}, clear=True):
            with patch('sys.argv', ['test']):
                injector = self.WindowsKeyboardInjector()
                self.assertFalse(injector.test_mode)
                with patch.object(injector, '_send_unicode') as mock_unicode:
                    injector.emit("test")
                    mock_unicode.assert_called_once_with("test")

    def test_emit_multiline(self):
        """Test emit with newlines."""
        with patch.dict(os.environ, {'TESTING': 'false', 'PYTEST_CURRENT_TEST': '', '_': ''}, clear=True):
            with patch('sys.argv', ['test']):
                injector = self.WindowsKeyboardInjector()
                self.assertFalse(injector.test_mode)
                with patch.object(injector, '_send_unicode') as mock_unicode:
                    with patch.object(injector, '_send_key') as mock_key:
                        injector.emit("line1\nline2")
                        self.assertEqual(mock_unicode.call_count, 2)
                        mock_unicode.assert_any_call("line1")
                        mock_unicode.assert_any_call("line2")
                        self.assertEqual(mock_key.call_count, 2)

    def test_emit_empty(self):
        """Test emit with empty string."""
        injector = self.WindowsKeyboardInjector()
        with patch.object(injector, '_send_unicode') as mock_unicode:
            injector.emit("")
            mock_unicode.assert_not_called()

    def test_test_mode_disables_operations(self):
        """Test that test mode disables keyboard operations."""
        with patch.dict(os.environ, {'TESTING': 'true'}):
            injector = self.WindowsKeyboardInjector()
            self.assertTrue(injector.test_mode)
            with patch.object(injector, '_send_key') as mock_key:
                injector.bksp(5)
                mock_key.assert_not_called()

    def test_error_handling_bksp(self):
        """Test error handling in bksp."""
        injector = self.WindowsKeyboardInjector()
        with patch.object(injector, '_send_key', side_effect=Exception("Test error")):
            with patch('sys.stderr'):
                injector.bksp(1)

    def test_error_handling_emit(self):
        """Test error handling in emit."""
        injector = self.WindowsKeyboardInjector()
        with patch.object(injector, '_send_unicode', side_effect=Exception("Test error")):
            with patch('sys.stderr'):
                injector.emit("test")


if __name__ == '__main__':
    unittest.main()