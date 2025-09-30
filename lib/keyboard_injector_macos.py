"""macOS implementation of KeyboardInjector interface using PyObjC."""

import sys
import os
import time
sys.path.append(os.path.join(os.path.dirname(__file__), 'xml-stream'))
from keyboard_injector import KeyboardInjector

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

        if config and config.xdotool_rate:
            # Convert Hz to milliseconds delay: delay = 1000 / rate
            self.typing_delay = int(1000 / config.xdotool_rate)
            if config.debug_enabled:
                print(f"[DEBUG] MacOSKeyboardInjector: typing_rate={config.xdotool_rate}Hz -> delay={self.typing_delay}ms", file=sys.stderr)
        else:
            self.typing_delay = typing_delay
            if config and config.debug_enabled:
                print(f"[DEBUG] MacOSKeyboardInjector: using default typing_delay={self.typing_delay}ms", file=sys.stderr)

        self.debug_enabled = config.debug_enabled if config else False

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

        print("\n" + "="*80, file=sys.stderr)
        print("❌ ACCESSIBILITY PERMISSION REQUIRED", file=sys.stderr)
        print("="*80, file=sys.stderr)
        print("QuickScribe needs accessibility permissions to inject keyboard events.", file=sys.stderr)
        print("\nTo grant permissions:", file=sys.stderr)
        print("1. Open System Settings → Privacy & Security → Accessibility", file=sys.stderr)
        print("2. Click the lock icon and enter your password", file=sys.stderr)
        print("3. Find and enable one of these apps:", file=sys.stderr)
        print("   • Terminal (if running from Terminal)", file=sys.stderr)
        print("   • Python (if running directly with python command)", file=sys.stderr)
        print("   • Your IDE (VS Code, PyCharm, etc. if running from IDE)", file=sys.stderr)
        print("4. Restart QuickScribe after granting permissions", file=sys.stderr)
        print("\nAlternatively, you can use clipboard mode by running with --no-injection", file=sys.stderr)
        print("="*80, file=sys.stderr)

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
                print(f"[DEBUG] MacOSKeyboardInjector: backspaced {count} characters", file=sys.stderr)

        except Exception as e:
            print(f"macOS backspace command failed: {str(e)}", file=sys.stderr)
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
                        print(f"[DEBUG] MacOSKeyboardInjector: emitted text: {repr(line)}", file=sys.stderr)

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
                        print(f"[DEBUG] MacOSKeyboardInjector: pressed Return key", file=sys.stderr)

                # Apply typing delay
                if self.typing_delay > 0:
                    time.sleep(self.typing_delay / 1000.0)

        except Exception as e:
            print(f"macOS text emission failed: {str(e)}", file=sys.stderr)
            if "accessibility" in str(e).lower() or "permission" in str(e).lower():
                self._show_permission_instructions()