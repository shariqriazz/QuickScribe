"""
Linux-style pr_* logging with streaming output support.

Priority-based message queuing:
- Critical messages (PR_EMERG through PR_ERR) display immediately
- Non-critical messages (PR_WARN through PR_DEBUG) queue during streaming

Streaming output properly cleans up when context exits or object goes out of scope.
"""

from colorama import Fore, Style, init
import sys
import threading
from collections import deque
from typing import Dict

init(autoreset=True)


# Log levels (single point of truth)
PR_EMERG   = 0
PR_ALERT   = 1
PR_CRIT    = 2
PR_ERR     = 3
PR_WARN    = 4
PR_NOTICE  = 5
PR_INFO    = 6
PR_DEBUG   = 7

# Immediate display threshold (single point of truth)
_IMMEDIATE_THRESHOLD = PR_ERR

# Color mapping (single point of truth) - BRIGHT for notice and above, normal for info/debug
_LEVEL_COLORS: Dict[int, str] = {
    PR_EMERG:  f"{Fore.RED}{Style.BRIGHT}",
    PR_ALERT:  f"{Fore.RED}{Style.BRIGHT}",
    PR_CRIT:   f"{Fore.RED}{Style.BRIGHT}",
    PR_ERR:    f"{Fore.RED}{Style.BRIGHT}",
    PR_WARN:   f"{Fore.YELLOW}{Style.BRIGHT}",
    PR_NOTICE: f"{Fore.CYAN}{Style.BRIGHT}",
    PR_INFO:   Fore.GREEN,
    PR_DEBUG:  Fore.BLUE,
}

# Symbol mapping (single point of truth)
_LEVEL_SYMBOLS: Dict[int, str] = {
    PR_EMERG:  "✗",
    PR_ALERT:  "✗",
    PR_CRIT:   "✗",
    PR_ERR:    "✗",
    PR_WARN:   "⚠",
    PR_NOTICE: "ℹ",
    PR_INFO:   "✓",
    PR_DEBUG:  "→",
}

# Prefix mapping (single point of truth)
_LEVEL_PREFIXES: Dict[int, str] = {
    PR_EMERG:  "EMERG: ",
    PR_ALERT:  "ALERT: ",
    PR_CRIT:   "CRIT: ",
    PR_ERR:    "",
    PR_WARN:   "",
    PR_NOTICE: "",
    PR_INFO:   "",
    PR_DEBUG:  "",
}

# Global state (single point of truth)
_current_log_level = PR_INFO
_streaming_active = False
_stream_lock = threading.Lock()
_queued_messages = deque()


def _format_message(level: int, msg: str) -> str:
    """
    Format log message with color, symbol, and prefix.

    Single point of truth for message formatting.
    """
    color = _LEVEL_COLORS[level]
    symbol = _LEVEL_SYMBOLS[level]
    prefix = _LEVEL_PREFIXES[level]
    formatted_msg = f"{color}{symbol} {prefix}{msg}{Style.RESET_ALL}"

    return formatted_msg


def _should_log(level: int) -> bool:
    """Check if message should be logged based on current log level."""
    return level <= _current_log_level


def _is_immediate(level: int) -> bool:
    """Check if message should display immediately (critical errors)."""
    return level <= _IMMEDIATE_THRESHOLD


def _display_message(level: int, msg: str):
    """
    Display formatted message to stderr.

    Single point of truth for message display.
    """
    formatted = _format_message(level, msg)
    print(formatted, file=sys.stderr)


def _flush_queue():
    """
    Flush all queued messages to stderr.

    Single point of truth for queue flushing.
    Called only after streaming completes.
    """
    while _queued_messages:
        level, msg = _queued_messages.popleft()
        _display_message(level, msg)


def _log_message(level: int, msg: str):
    """
    Route message based on priority and streaming state.

    Single point of truth for message routing logic.

    Critical messages (<=PR_ERR): display immediately
    Non-critical messages (>PR_ERR): queue during streaming, immediate otherwise
    """
    if not _should_log(level):
        return

    with _stream_lock:
        if _is_immediate(level):
            _display_message(level, msg)
        elif _streaming_active:
            _queued_messages.append((level, msg))
        else:
            _display_message(level, msg)


class StreamingOutputHandler:
    """
    Context manager for streaming output with message queuing.

    Single point of truth for streaming state management.

    Automatically flushes queue and ends stream when:
    - Context exits normally (with statement ends)
    - Context exits due to exception
    - Object goes out of scope (__del__ called)

    Usage:
        with get_streaming_handler() as stream:
            stream.write("streaming content")
            pr_info("this will queue")
            pr_err("this displays immediately")
    """

    def __init__(self):
        self._active = False
        self._last_full_text = ""

    def __enter__(self):
        global _streaming_active

        with _stream_lock:
            _streaming_active = True
            self._active = True

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._cleanup()

        return False

    def __del__(self):
        """Ensure cleanup if object goes out of scope without proper context exit."""
        if self._active:
            self._cleanup()

    def _cleanup(self):
        """
        Internal cleanup method.

        Ends streaming, prints trailing newline, flushes queue.
        Single point of truth for stream cleanup.
        """
        global _streaming_active

        if not self._active:
            return

        with _stream_lock:
            _streaming_active = False
            self._active = False

        # Trailing newline after streaming ends (single point of truth)
        print(flush=True)

        with _stream_lock:
            _flush_queue()

    def _common_prefix_length(self, old: str, new: str) -> int:
        """Calculate length of common prefix between two strings."""
        for i, (c1, c2) in enumerate(zip(old, new)):
            if c1 != c2:
                return i
        return min(len(old), len(new))

    def write(self, text: str):
        """Write streaming content without newline (standard white color)."""
        if not text:
            return

        print(f"{Fore.WHITE}{text}{Style.RESET_ALL}", end='', flush=True)

    def write_full(self, text: str):
        """Write full text update, backspacing to common prefix."""
        if not text:
            return

        prefix_len = self._common_prefix_length(self._last_full_text, text)
        backspace_count = len(self._last_full_text) - prefix_len
        new_suffix = text[prefix_len:]

        if backspace_count > 0:
            print('\b' * backspace_count, end='', flush=True)

        if new_suffix:
            print(f"{Fore.WHITE}{new_suffix}{Style.RESET_ALL}", end='', flush=True)

        self._last_full_text = text


def pr_emerg(msg: str):
    """Emergency: system unusable - IMMEDIATE display."""
    _log_message(PR_EMERG, msg)


def pr_alert(msg: str):
    """Alert: action required immediately - IMMEDIATE display."""
    _log_message(PR_ALERT, msg)


def pr_crit(msg: str):
    """Critical conditions - IMMEDIATE display."""
    _log_message(PR_CRIT, msg)


def pr_err(msg: str):
    """Error conditions - IMMEDIATE display."""
    _log_message(PR_ERR, msg)


def pr_warn(msg: str):
    """Warning conditions - QUEUED during streaming."""
    _log_message(PR_WARN, msg)


def pr_notice(msg: str):
    """Normal but significant - QUEUED during streaming."""
    _log_message(PR_NOTICE, msg)


def pr_info(msg: str):
    """Informational - QUEUED during streaming."""
    _log_message(PR_INFO, msg)


def pr_debug(msg: str):
    """Debug-level messages - QUEUED during streaming."""
    _log_message(PR_DEBUG, msg)


def set_log_level(level: int):
    """
    Set global log level.

    Args:
        level: Log level (0-7, PR_EMERG through PR_DEBUG)
    """
    global _current_log_level

    if not (PR_EMERG <= level <= PR_DEBUG):
        pr_warn(f"Invalid log level {level}, using PR_INFO")
        _current_log_level = PR_INFO
    else:
        _current_log_level = level


def get_streaming_handler() -> StreamingOutputHandler:
    """
    Get streaming output handler context manager.

    Returns:
        StreamingOutputHandler instance for use with 'with' statement
    """
    return StreamingOutputHandler()
