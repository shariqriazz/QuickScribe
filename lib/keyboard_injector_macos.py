"""macOS implementation of KeyboardInjector interface using PyObjC."""

import sys
import os
import time
sys.path.append(os.path.join(os.path.dirname(__file__), 'xml-stream'))
from keyboard_injector import KeyboardInjector
sys.path.insert(0, os.path.dirname(__file__))
from pr_log import pr_err, pr_alert, pr_debug

try:
    from Quartz.CoreGraphics import (
        CGEventCreateKeyboardEvent,
        CGEventKeyboardSetUnicodeString,
        CGEventPost,
        kCGHIDEventTap
    )
    from ApplicationServices import AXIsProcessTrusted
    PYOBJC_AVAILABLE = True
except ImportError:
    PYOBJC_AVAILABLE = False


class MacOSKeyboardInjector(KeyboardInjector):
    """macOS-based keyboard injector using Core Graphics Event APIs."""

    # Virtual key codes for macOS
    VK_DELETE = 0x33  # Backspace/Delete key
    VK_RETURN = 0x24  # Return/Enter key

    def __init__(self, config=None, typing_delay: int = 5):
        """
        Initialize macOS keyboard injector.

        Args:
            config: Configuration object with xdotool_rate and debug_enabled
            typing_delay: Default millisecond delay between keystrokes if no config
        """
        if not PYOBJC_AVAILABLE:
            raise ImportError("PyObjC framework not available. Install pyobjc-framework-Quartz.")

        xdotool_rate = getattr(config, 'xdotool_rate', None) if config else None
        if xdotool_rate:
            # Convert Hz to milliseconds delay: delay = 1000 / rate
            self.typing_delay = int(1000 / xdotool_rate)
            if getattr(config, 'debug_enabled', False):
                pr_debug(f"MacOSKeyboardInjector: typing_rate={xdotool_rate}Hz -> delay={self.typing_delay}ms")
        else:
            self.typing_delay = typing_delay
            if config and getattr(config, 'debug_enabled', False):
                pr_debug(f"MacOSKeyboardInjector: using default typing_delay={self.typing_delay}ms")

        self.debug_enabled = getattr(config, 'debug_enabled', False) if config else False

        # Detect if we're running in test mode
        self.test_mode = (
            os.getenv("TESTING", "false").lower() == "true" or
            "pytest" in os.getenv("_", "") or
            "pytest" in str(os.getenv("PYTEST_CURRENT_TEST", "")) or
            any("pytest" in arg for arg in sys.argv if arg)
        )

        # Track if we've already shown permission warning to avoid spam
        self.permission_warning_shown = False

    def _check_accessibility_permissions(self) -> bool:
        """Check if the process has accessibility permissions."""
        try:
            return AXIsProcessTrusted()
        except Exception:
            return False

    def _show_permission_instructions(self) -> None:
        """Display instructions for granting accessibility permissions."""
        if self.permission_warning_shown:
            return

        pr_alert("="*80)
        pr_alert("ACCESSIBILITY PERMISSION REQUIRED")
        pr_alert("="*80)
        pr_alert("QuickScribe needs accessibility permissions to inject keyboard events.")
        pr_alert("To grant permissions:")
        pr_alert("1. Open System Settings → Privacy & Security → Accessibility")
        pr_alert("2. Click the lock icon and enter your password")
        pr_alert("3. Find and enable one of these apps:")
        pr_alert("   • Terminal (if running from Terminal)")
        pr_alert("   • Python (if running directly with python command)")
        pr_alert("   • Your IDE (VS Code, PyCharm, etc. if running from IDE)")
        pr_alert("4. Restart QuickScribe after granting permissions")
        pr_alert("Alternatively, you can use clipboard mode by running with --no-injection")
        pr_alert("="*80)

        self.permission_warning_shown = True

    def bksp(self, count: int) -> None:
        """Backspace count characters using CGEvent APIs."""
        if self.test_mode or count <= 0:
            return

        # Check accessibility permissions before attempting injection
        if not self._check_accessibility_permissions():
            self._show_permission_instructions()
            return

        try:
            for _ in range(count):
                # Create key down event for Delete key
                event_down = CGEventCreateKeyboardEvent(None, self.VK_DELETE, True)
                if event_down is None:
                    raise RuntimeError("Failed to create keyboard event - check accessibility permissions")

                result = CGEventPost(kCGHIDEventTap, event_down)
                if result != 0:
                    raise RuntimeError(f"Failed to post keyboard event (error code: {result})")

                # Create key up event for Delete key
                event_up = CGEventCreateKeyboardEvent(None, self.VK_DELETE, False)
                if event_up is None:
                    raise RuntimeError("Failed to create keyboard event - check accessibility permissions")

                result = CGEventPost(kCGHIDEventTap, event_up)
                if result != 0:
                    raise RuntimeError(f"Failed to post keyboard event (error code: {result})")

                # Apply typing delay between keypresses
                if self.typing_delay > 0:
                    time.sleep(self.typing_delay / 1000.0)

            if self.debug_enabled:
                pr_debug(f"MacOSKeyboardInjector: backspaced {count} characters")

        except Exception as e:
            pr_err(f"macOS backspace command failed: {str(e)}")
            if "accessibility" in str(e).lower() or "permission" in str(e).lower():
                self._show_permission_instructions()

    def emit(self, text: str) -> None:
        """Emit text at current cursor position using CGEvent APIs."""
        if self.test_mode or not text:
            return

        # Check accessibility permissions before attempting injection
        if not self._check_accessibility_permissions():
            self._show_permission_instructions()
            return

        try:
            lines = text.split('\n')
            for i, line in enumerate(lines):
                if line:
                    # Create keyboard event and set Unicode string
                    event = CGEventCreateKeyboardEvent(None, 0, True)
                    if event is None:
                        raise RuntimeError("Failed to create keyboard event - check accessibility permissions")

                    CGEventKeyboardSetUnicodeString(event, len(line), line)
                    result = CGEventPost(kCGHIDEventTap, event)
                    if result != 0:
                        raise RuntimeError(f"Failed to post keyboard event (error code: {result})")

                    if self.debug_enabled:
                        pr_debug(f"MacOSKeyboardInjector: emitted text: {repr(line)}")

                # If it's not the last line, press Enter
                if i < len(lines) - 1:
                    event_return_down = CGEventCreateKeyboardEvent(None, self.VK_RETURN, True)
                    if event_return_down is None:
                        raise RuntimeError("Failed to create return key event - check accessibility permissions")

                    result = CGEventPost(kCGHIDEventTap, event_return_down)
                    if result != 0:
                        raise RuntimeError(f"Failed to post return key event (error code: {result})")

                    event_return_up = CGEventCreateKeyboardEvent(None, self.VK_RETURN, False)
                    if event_return_up is None:
                        raise RuntimeError("Failed to create return key event - check accessibility permissions")

                    result = CGEventPost(kCGHIDEventTap, event_return_up)
                    if result != 0:
                        raise RuntimeError(f"Failed to post return key event (error code: {result})")

                    if self.debug_enabled:
                        pr_debug("MacOSKeyboardInjector: pressed Return key")

                # Apply typing delay
                if self.typing_delay > 0:
                    time.sleep(self.typing_delay / 1000.0)

        except Exception as e:
            pr_err(f"macOS text emission failed: {str(e)}")
            if "accessibility" in str(e).lower() or "permission" in str(e).lower():
                self._show_permission_instructions()