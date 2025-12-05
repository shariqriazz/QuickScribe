"""Windows implementation of KeyboardInjector interface using ctypes and SendInput."""

import sys
import os
import time
import ctypes
from ctypes import wintypes
sys.path.append(os.path.join(os.path.dirname(__file__), 'xml-stream'))
from keyboard_injector import KeyboardInjector
sys.path.insert(0, os.path.dirname(__file__))
from pr_log import pr_err, pr_debug


try:
    user32 = ctypes.WinDLL('user32', use_last_error=True)

    INPUT_KEYBOARD = 1
    KEYEVENTF_UNICODE = 0x0004
    KEYEVENTF_KEYUP = 0x0002

    VK_BACK = 0x08
    VK_RETURN = 0x0D

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [
            ("wVk", wintypes.WORD),
            ("wScan", wintypes.WORD),
            ("dwFlags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG))
        ]

    class INPUT(ctypes.Structure):
        class _INPUT(ctypes.Union):
            _fields_ = [("ki", KEYBDINPUT)]

        _anonymous_ = ("_input",)
        _fields_ = [
            ("type", wintypes.DWORD),
            ("_input", _INPUT)
        ]

    CTYPES_AVAILABLE = True
except (OSError, AttributeError):
    CTYPES_AVAILABLE = False


class WindowsKeyboardInjector(KeyboardInjector):
    """Windows-based keyboard injector using SendInput API."""

    def __init__(self, config=None, typing_delay: int = 5):
        """
        Initialize Windows keyboard injector.

        Args:
            config: Configuration object with xdotool_rate and debug_enabled
            typing_delay: Default millisecond delay between keystrokes if no config
        """
        if not CTYPES_AVAILABLE:
            raise ImportError("Windows ctypes/user32 not available.")

        xdotool_rate = getattr(config, 'xdotool_rate', None) if config else None
        if xdotool_rate:
            self.typing_delay = int(1000 / xdotool_rate)
            if getattr(config, 'debug_enabled', False):
                pr_debug(f"WindowsKeyboardInjector: typing_rate={xdotool_rate}Hz -> delay={self.typing_delay}ms")
        else:
            self.typing_delay = typing_delay
            if config and getattr(config, 'debug_enabled', False):
                pr_debug(f"WindowsKeyboardInjector: using default typing_delay={self.typing_delay}ms")

        self.debug_enabled = getattr(config, 'debug_enabled', False) if config else False

        self.test_mode = (
            os.getenv("TESTING", "false").lower() == "true" or
            "pytest" in os.getenv("_", "") or
            "pytest" in str(os.getenv("PYTEST_CURRENT_TEST", "")) or
            any("pytest" in arg for arg in sys.argv if arg)
        )

    def _send_key(self, vk_code: int, key_up: bool = False) -> None:
        """Send a virtual key code using SendInput."""
        extra = ctypes.pointer(wintypes.ULONG(0))
        ki = KEYBDINPUT(
            wVk=vk_code,
            wScan=0,
            dwFlags=KEYEVENTF_KEYUP if key_up else 0,
            time=0,
            dwExtraInfo=extra
        )
        inp = INPUT(type=INPUT_KEYBOARD, ki=ki)
        result = user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))
        if result != 1:
            raise RuntimeError(f"SendInput failed with result: {result}")

    def _send_unicode(self, char: str) -> None:
        """Send a Unicode character using SendInput."""
        extra = ctypes.pointer(wintypes.ULONG(0))
        for c in char:
            code_point = ord(c)

            ki_down = KEYBDINPUT(
                wVk=0,
                wScan=code_point,
                dwFlags=KEYEVENTF_UNICODE,
                time=0,
                dwExtraInfo=extra
            )
            inp_down = INPUT(type=INPUT_KEYBOARD, ki=ki_down)

            ki_up = KEYBDINPUT(
                wVk=0,
                wScan=code_point,
                dwFlags=KEYEVENTF_UNICODE | KEYEVENTF_KEYUP,
                time=0,
                dwExtraInfo=extra
            )
            inp_up = INPUT(type=INPUT_KEYBOARD, ki=ki_up)

            result = user32.SendInput(1, ctypes.byref(inp_down), ctypes.sizeof(inp_down))
            if result != 1:
                raise RuntimeError(f"SendInput failed for key down: {result}")

            result = user32.SendInput(1, ctypes.byref(inp_up), ctypes.sizeof(inp_up))
            if result != 1:
                raise RuntimeError(f"SendInput failed for key up: {result}")

    def bksp(self, count: int) -> None:
        """Backspace count characters using SendInput."""
        if self.test_mode or count <= 0:
            return

        try:
            for _ in range(count):
                self._send_key(VK_BACK, key_up=False)
                self._send_key(VK_BACK, key_up=True)

                if self.typing_delay > 0:
                    time.sleep(self.typing_delay / 1000.0)

            if self.debug_enabled:
                pr_debug(f"WindowsKeyboardInjector: backspaced {count} characters")

        except Exception as e:
            pr_err(f"Windows backspace command failed: {str(e)}")

    def emit(self, text: str) -> None:
        """Emit text at current cursor position using SendInput."""
        if self.test_mode or not text:
            return

        try:
            lines = text.split('\n')
            for i, line in enumerate(lines):
                if line:
                    self._send_unicode(line)

                    if self.debug_enabled:
                        pr_debug(f"WindowsKeyboardInjector: emitted text: {repr(line)}")

                if i < len(lines) - 1:
                    self._send_key(VK_RETURN, key_up=False)
                    self._send_key(VK_RETURN, key_up=True)

                    if self.debug_enabled:
                        pr_debug("WindowsKeyboardInjector: pressed Return key")

                if self.typing_delay > 0:
                    time.sleep(self.typing_delay / 1000.0)

        except Exception as e:
            pr_err(f"Windows text emission failed: {str(e)}")