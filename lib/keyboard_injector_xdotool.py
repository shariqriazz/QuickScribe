"""Xdotool implementation of KeyboardInjector interface."""

import subprocess
import os
import sys
import time
import threading
sys.path.append(os.path.join(os.path.dirname(__file__), 'xml-stream'))
from keyboard_injector import KeyboardInjector
sys.path.insert(0, os.path.dirname(__file__))
from pr_log import pr_err, pr_debug
from pynput import keyboard


class ModifierStateTracker:
    """Tracks modifier key states using pynput keyboard listener."""

    def __init__(self):
        self._modifiers = {
            'ctrl': False,
            'alt': False,
            'shift': False,
            'super': False
        }
        self._lock = threading.Lock()
        self._no_modifiers_event = threading.Event()
        self._no_modifiers_event.set()

        self._listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release
        )
        self._listener.start()

    def _on_press(self, key):
        with self._lock:
            if key in (keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
                self._modifiers['ctrl'] = True
            elif key in (keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r):
                self._modifiers['alt'] = True
            elif key in (keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r):
                self._modifiers['shift'] = True
            elif key in (keyboard.Key.cmd, keyboard.Key.cmd_l, keyboard.Key.cmd_r):
                self._modifiers['super'] = True

            if any(self._modifiers.values()):
                self._no_modifiers_event.clear()

    def _on_release(self, key):
        with self._lock:
            if key in (keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
                self._modifiers['ctrl'] = False
            elif key in (keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r):
                self._modifiers['alt'] = False
            elif key in (keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r):
                self._modifiers['shift'] = False
            elif key in (keyboard.Key.cmd, keyboard.Key.cmd_l, keyboard.Key.cmd_r):
                self._modifiers['super'] = False

            if not any(self._modifiers.values()):
                self._no_modifiers_event.set()

    def wait_for_no_modifiers(self) -> None:
        """Block until all modifier keys are released, then wait additional 100ms for propagation."""
        had_to_wait = not self._no_modifiers_event.is_set()
        self._no_modifiers_event.wait()
        if had_to_wait:
            time.sleep(0.1)

    def stop(self) -> None:
        """Stop the keyboard listener."""
        self._listener.stop()


class XdotoolKeyboardInjector(KeyboardInjector):
    """Xdotool-based keyboard injector for direct system keyboard operations."""
    
    def __init__(self, config=None, typing_delay: int = 5):
        """
        Initialize xdotool keyboard injector.

        Args:
            config: Configuration object with xdotool_rate and debug_enabled
            typing_delay: Default millisecond delay between keystrokes if no config
        """
        xdotool_rate = getattr(config, 'xdotool_rate', None) if config else None
        if xdotool_rate:
            # Convert Hz to milliseconds delay: delay = 1000 / rate
            self.typing_delay = int(1000 / xdotool_rate)
            if getattr(config, 'debug_enabled', False):
                pr_debug(f"XdotoolKeyboardInjector: typing_rate={xdotool_rate}Hz -> delay={self.typing_delay}ms")
        else:
            self.typing_delay = typing_delay
            if config and getattr(config, 'debug_enabled', False):
                pr_debug(f"XdotoolKeyboardInjector: using default typing_delay={self.typing_delay}ms")
        self.debug_enabled = getattr(config, 'debug_enabled', False) if config else False
        self.test_mode = (
            os.getenv("TESTING", "false").lower() == "true" or
            "pytest" in os.getenv("_", "") or
            "pytest" in str(os.getenv("PYTEST_CURRENT_TEST", "")) or
            any("pytest" in arg for arg in sys.argv if arg)
        )
        self._modifier_tracker = ModifierStateTracker()

    def _run_xdotool(self, cmd: list) -> None:
        """Execute xdotool command after waiting for modifier keys to be released."""
        self._modifier_tracker.wait_for_no_modifiers()

        try:
            if self.debug_enabled:
                pr_debug(f"xdotool command: {' '.join(cmd)}")
            subprocess.run(cmd, check=True, capture_output=True, text=True)
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            pr_err(f"xdotool command failed: {str(e)}")

    def bksp(self, count: int) -> None:
        """Backspace count characters."""
        if self.test_mode or count <= 0:
            return

        cmd = [
            "xdotool", "key",
            "--delay", str(self.typing_delay),
            "--repeat", str(count),
            "BackSpace"
        ]
        self._run_xdotool(cmd)
    
    def emit(self, text: str) -> None:
        """Emit text at current cursor position."""
        if self.test_mode or not text:
            return

        lines = text.split('\n')
        for i, line in enumerate(lines):
            if line:
                cmd = [
                    "xdotool", "type",
                    "--delay", str(self.typing_delay),
                    "--",
                    line
                ]
                self._run_xdotool(cmd)

            if i < len(lines) - 1:
                cmd = ["xdotool", "key", "Return"]
                self._run_xdotool(cmd)

    def __del__(self):
        """Cleanup modifier tracker on destruction."""
        if hasattr(self, '_modifier_tracker'):
            self._modifier_tracker.stop()