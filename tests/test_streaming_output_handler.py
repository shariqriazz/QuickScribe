"""
Test StreamingOutputHandler with backspace-based full updates.
"""
import unittest
from unittest.mock import patch, call
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from lib.pr_log import get_streaming_handler, StreamingOutputHandler
from colorama import Fore, Style


class TestStreamingOutputHandler(unittest.TestCase):
    """Test streaming output handler with mocked print."""

    @patch('builtins.print')
    def test_incremental_write(self, mock_print):
        """Test incremental write mode without backspaces."""
        with get_streaming_handler() as stream:
            stream.write("Hello")
            stream.write(" World")

        calls = mock_print.call_args_list

        self.assertEqual(calls[0], call(f"{Fore.WHITE}Hello{Style.RESET_ALL}", end='', flush=True))
        self.assertEqual(calls[1], call(f"{Fore.WHITE} World{Style.RESET_ALL}", end='', flush=True))
        self.assertEqual(calls[2], call(flush=True))

    @patch('builtins.print')
    def test_full_update_write(self, mock_print):
        """Test full update mode with backspaces to common prefix."""
        with get_streaming_handler() as stream:
            stream.write_full("partial")
            stream.write_full("partial text")
            stream.write_full("complete text")

        calls = mock_print.call_args_list

        self.assertEqual(calls[0], call(f"{Fore.WHITE}partial{Style.RESET_ALL}", end='', flush=True))

        self.assertEqual(calls[1], call(f"{Fore.WHITE} text{Style.RESET_ALL}", end='', flush=True))

        self.assertEqual(calls[2], call('\b' * 12, end='', flush=True))
        self.assertEqual(calls[3], call(f"{Fore.WHITE}complete text{Style.RESET_ALL}", end='', flush=True))

        self.assertEqual(calls[4], call(flush=True))

    @patch('builtins.print')
    def test_mixed_write_modes(self, mock_print):
        """Test mixing incremental and full update modes."""
        with get_streaming_handler() as stream:
            stream.write("Start")
            stream.write_full("Override")
            stream.write(" append")

        calls = mock_print.call_args_list

        self.assertEqual(calls[0], call(f"{Fore.WHITE}Start{Style.RESET_ALL}", end='', flush=True))

        self.assertEqual(calls[1], call(f"{Fore.WHITE}Override{Style.RESET_ALL}", end='', flush=True))

        self.assertEqual(calls[2], call(f"{Fore.WHITE} append{Style.RESET_ALL}", end='', flush=True))

        self.assertEqual(calls[3], call(flush=True))

    @patch('builtins.print')
    def test_backspace_to_common_prefix(self, mock_print):
        """Test backspace calculation to common prefix."""
        with get_streaming_handler() as stream:
            stream.write_full("hello world")
            stream.write_full("hello there")

        calls = mock_print.call_args_list

        self.assertEqual(calls[0], call(f"{Fore.WHITE}hello world{Style.RESET_ALL}", end='', flush=True))

        self.assertEqual(calls[1], call('\b' * 5, end='', flush=True))
        self.assertEqual(calls[2], call(f"{Fore.WHITE}there{Style.RESET_ALL}", end='', flush=True))

        self.assertEqual(calls[3], call(flush=True))

    @patch('builtins.print')
    def test_empty_string_handling(self, mock_print):
        """Test that empty strings are skipped."""
        with get_streaming_handler() as stream:
            stream.write("")
            stream.write_full("")

        calls = mock_print.call_args_list

        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0], call(flush=True))

    @patch('builtins.print')
    def test_vosk_simulation(self, mock_print):
        """Simulate VOSK partial result updates."""
        with get_streaming_handler() as stream:
            stream.write_full("hello")
            stream.write_full("hello wo")
            stream.write_full("hello world")
            stream.write_full("hello world ")
            stream.write_full("hello world test")

        calls = mock_print.call_args_list

        self.assertEqual(calls[0], call(f"{Fore.WHITE}hello{Style.RESET_ALL}", end='', flush=True))

        self.assertEqual(calls[1], call(f"{Fore.WHITE} wo{Style.RESET_ALL}", end='', flush=True))

        self.assertEqual(calls[2], call(f"{Fore.WHITE}rld{Style.RESET_ALL}", end='', flush=True))

        self.assertEqual(calls[3], call(f"{Fore.WHITE} {Style.RESET_ALL}", end='', flush=True))

        self.assertEqual(calls[4], call(f"{Fore.WHITE}test{Style.RESET_ALL}", end='', flush=True))

        self.assertEqual(calls[5], call(flush=True))

    @patch('builtins.print')
    def test_final_newline_always_printed(self, mock_print):
        """Test that final newline is always printed on exit."""
        with get_streaming_handler() as stream:
            stream.write("content")

        calls = mock_print.call_args_list
        self.assertEqual(calls[-1], call(flush=True))

    @patch('builtins.print')
    def test_common_prefix_length_calculation(self, mock_print):
        """Test _common_prefix_length helper method."""
        handler = StreamingOutputHandler()

        self.assertEqual(handler._common_prefix_length("", ""), 0)
        self.assertEqual(handler._common_prefix_length("", "test"), 0)
        self.assertEqual(handler._common_prefix_length("test", ""), 0)
        self.assertEqual(handler._common_prefix_length("test", "test"), 4)
        self.assertEqual(handler._common_prefix_length("testing", "test"), 4)
        self.assertEqual(handler._common_prefix_length("test", "testing"), 4)
        self.assertEqual(handler._common_prefix_length("hello world", "hello there"), 6)
        self.assertEqual(handler._common_prefix_length("abc", "xyz"), 0)


if __name__ == "__main__":
    unittest.main()
