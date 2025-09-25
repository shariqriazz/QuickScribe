"""Xdotool implementation of KeyboardInjector interface."""

import subprocess
import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), 'xml-stream'))
from keyboard_injector import KeyboardInjector


class XdotoolKeyboardInjector(KeyboardInjector):
    """Xdotool-based keyboard injector for direct system keyboard operations."""
    
    def __init__(self, typing_delay: int = 5):
        """
        Initialize xdotool keyboard injector.
        
        Args:
            typing_delay: Millisecond delay between keystrokes
        """
        self.typing_delay = typing_delay
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
            subprocess.run([
                "xdotool", "key",
                "--delay", str(self.typing_delay),
                "--repeat", str(count),
                "BackSpace"
            ], check=True, capture_output=True, text=True)
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
                    subprocess.run([
                        "xdotool", "type",
                        "--delay", str(self.typing_delay),
                        line
                    ], check=True, capture_output=True, text=True)
                
                # If it's not the last line, press Enter
                if i < len(lines) - 1:
                    subprocess.run(["xdotool", "key", "Return"], 
                                 check=True, capture_output=True, text=True)
                                 
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            print(f"xdotool type command failed: {str(e)}", file=sys.stderr)