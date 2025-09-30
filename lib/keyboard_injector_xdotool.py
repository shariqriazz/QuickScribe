"""Xdotool implementation of KeyboardInjector interface."""

import subprocess
import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), 'xml-stream'))
from keyboard_injector import KeyboardInjector


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
                print(f"[DEBUG] XdotoolKeyboardInjector: typing_rate={xdotool_rate}Hz -> delay={self.typing_delay}ms", file=sys.stderr)
        else:
            self.typing_delay = typing_delay
            if config and getattr(config, 'debug_enabled', False):
                print(f"[DEBUG] XdotoolKeyboardInjector: using default typing_delay={self.typing_delay}ms", file=sys.stderr)
        self.debug_enabled = getattr(config, 'debug_enabled', False) if config else False
        # Detect if we're running in test mode
        self.test_mode = (
            os.getenv("TESTING", "false").lower() == "true" or 
            "pytest" in os.getenv("_", "") or
            "pytest" in str(os.getenv("PYTEST_CURRENT_TEST", "")) or
            any("pytest" in arg for arg in sys.argv if arg)
        )
    
    def bksp(self, count: int) -> None:
        """Backspace count characters."""
        if self.test_mode or count <= 0:
            return
            
        try:
            cmd = [
                "xdotool", "key",
                "--delay", str(self.typing_delay),
                "--repeat", str(count),
                "BackSpace"
            ]
            if self.debug_enabled:
                print(f"[DEBUG] xdotool bksp command: {' '.join(cmd)}", file=sys.stderr)
            subprocess.run(cmd, check=True, capture_output=True, text=True)
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            print(f"xdotool backspace command failed: {str(e)}", file=sys.stderr)
    
    def emit(self, text: str) -> None:
        """Emit text at current cursor position."""
        if self.test_mode or not text:
            return
        
        try:
            lines = text.split('\n')
            for i, line in enumerate(lines):
                if line:
                    cmd = [
                        "xdotool", "type",
                        "--delay", str(self.typing_delay),
                        line
                    ]
                    if self.debug_enabled:
                        print(f"[DEBUG] xdotool type command: {' '.join(cmd)}", file=sys.stderr)
                    subprocess.run(cmd, check=True, capture_output=True, text=True)
                
                # If it's not the last line, press Enter
                if i < len(lines) - 1:
                    cmd = ["xdotool", "key", "Return"]
                    if self.debug_enabled:
                        print(f"[DEBUG] xdotool key command: {' '.join(cmd)}", file=sys.stderr)
                    subprocess.run(cmd, check=True, capture_output=True, text=True)
                                 
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            print(f"xdotool type command failed: {str(e)}", file=sys.stderr)