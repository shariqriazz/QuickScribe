"""
Tests for output_manager module.
"""

import unittest
from unittest.mock import patch, call
import subprocess

from lib.output_manager import OutputManager, XdotoolError
from lib.diff_engine import DiffResult


class TestOutputManager(unittest.TestCase):
    """Test cases for OutputManager class."""

    def setUp(self):
        """Set up test fixtures."""
        self.manager = OutputManager(xdotool_cmd="xdotool", typing_delay=12)

    @patch('subprocess.run')
    def test_backspace_command_construction(self, mock_run):
        """Test backspace command is constructed correctly."""
        self.manager.backspace(3)
        mock_run.assert_called_once_with(
            ['xdotool', 'key', '--delay', '12', '--repeat', '3', 'BackSpace'],
            check=True, capture_output=True, text=True
        )

    @patch('subprocess.run')
    def test_type_text_command_construction(self, mock_run):
        """Test type command is constructed correctly."""
        self.manager.type_text("test")
        mock_run.assert_called_once_with(
            ['xdotool', 'type', '--delay', '12', 'test'],
            check=True, capture_output=True, text=True
        )

    @patch('subprocess.run')
    def test_execute_diff_command_sequence(self, mock_run):
        """Test execute_diff calls commands in correct sequence."""
        diff = DiffResult(backspaces=2, new_text="new")
        self.manager.execute_diff(diff)
        
        expected_calls = [
            call(['xdotool', 'key', '--delay', '12', '--repeat', '2', 'BackSpace'],
                 check=True, capture_output=True, text=True),
            call(['xdotool', 'type', '--delay', '12', 'new'],
                 check=True, capture_output=True, text=True)
        ]
        self.assertEqual(mock_run.call_args_list, expected_calls)

    @patch('subprocess.run')
    def test_empty_text_no_command(self, mock_run):
        """Test that empty text does not execute type command."""
        self.manager.type_text("")
        mock_run.assert_not_called()

    @patch('subprocess.run')
    def test_zero_backspace_no_command(self, mock_run):
        """Test that zero backspaces does not execute command."""
        self.manager.backspace(0)
        mock_run.assert_not_called()

    def test_negative_backspace_raises_error(self):
        """Test that negative backspace count raises ValueError."""
        with self.assertRaises(ValueError):
            self.manager.backspace(-1)

    @patch('subprocess.run')
    def test_xdotool_command_failure(self, mock_run):
        """Test that xdotool command failure raises XdotoolError."""
        mock_run.side_effect = subprocess.CalledProcessError(1, 'cmd')
        with self.assertRaises(XdotoolError):
            self.manager.type_text("test")

    @patch('subprocess.run')
    def test_xdotool_not_found(self, mock_run):
        """Test that missing xdotool executable raises XdotoolError."""
        mock_run.side_effect = FileNotFoundError()
        with self.assertRaises(XdotoolError):
            self.manager.type_text("test")

    @patch('subprocess.run')
    def test_unicode_text_handling(self, mock_run):
        """Test handling of unicode text."""
        self.manager.type_text("Hello 世界")
        mock_run.assert_called_once_with(
            ['xdotool', 'type', '--delay', '12', 'Hello 世界'],
            check=True, capture_output=True, text=True
        )

    @patch('subprocess.run')
    def test_special_characters_handling(self, mock_run):
        """Test handling of special characters."""
        self.manager.type_text("Hello, @#$%^&*()")
        mock_run.assert_called_once_with(
            ['xdotool', 'type', '--delay', '12', 'Hello, @#$%^&*()'],
            check=True, capture_output=True, text=True
        )

    @patch('subprocess.run')
    def test_empty_diff_no_commands(self, mock_run):
        """Test that empty diff result executes no commands."""
        diff = DiffResult(backspaces=0, new_text="")
        self.manager.execute_diff(diff)
        mock_run.assert_not_called()

    @patch('subprocess.run')
    def test_custom_typing_delay(self, mock_run):
        """Test that custom typing delay is respected."""
        manager = OutputManager(typing_delay=50)
        manager.type_text("test")
        mock_run.assert_called_once_with(
            ['xdotool', 'type', '--delay', '50', 'test'],
            check=True, capture_output=True, text=True
        )