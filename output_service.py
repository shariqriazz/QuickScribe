"""
Output Service - Handles text output via xdotool or clipboard.
"""
import subprocess
import platform
from pynput import keyboard

try:
    import pyperclip
except ImportError:
    print("Error: pyperclip library not found. Please install it: pip install pyperclip")
    import sys
    sys.exit(1)


class OutputService:
    """Handles text output using xdotool or clipboard methods."""
    
    def __init__(self, use_xdotool=False):
        self.use_xdotool = use_xdotool
        self.last_typed_text = ""
        self.keyboard_controller = keyboard.Controller()
        
        # Check platform compatibility for xdotool
        if self.use_xdotool and platform.system() != "Linux":
            print(f"\nWarning: xdotool is only supported on Linux. Using clipboard method instead.", file=sys.stderr)
            self.use_xdotool = False
    
    def type_with_xdotool(self, new_text):
        """Uses xdotool to type text directly with editing support via backspace."""
        try:
            # Find the common prefix between previous and new text
            common_prefix_length = 0
            for i in range(min(len(self.last_typed_text), len(new_text))):
                if self.last_typed_text[i] == new_text[i]:
                    common_prefix_length += 1
                else:
                    break
            
            # Calculate backspaces needed
            backspaces_needed = len(self.last_typed_text) - common_prefix_length
            
            # Text to add after backspacing
            text_to_add = new_text[common_prefix_length:]
            
            # Send backspaces to delete from cursor to common point
            if backspaces_needed > 0:
                subprocess.run(["xdotool", "key", "--repeat", str(backspaces_needed), "BackSpace"], 
                              capture_output=True, text=True, check=True)
            
            # Type the new text
            if text_to_add:
                subprocess.run(["xdotool", "type", text_to_add], 
                              capture_output=True, text=True, check=True)
            
            # Update our record of what was typed
            self.last_typed_text = new_text
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"\nError executing xdotool: {e}", file=sys.stderr)
            print("Make sure xdotool is installed: sudo apt-get install xdotool", file=sys.stderr)
            return False
        except FileNotFoundError:
            print("\nxdotool command not found. Please install it: sudo apt-get install xdotool", file=sys.stderr)
            return False
        except Exception as e:
            print(f"\nUnexpected error using xdotool: {e}", file=sys.stderr)
            return False
    
    def output_text_cross_platform(self, text):
        """Outputs text using either xdotool or clipboard paste based on settings."""
        current_os = platform.system()
        
        # Use xdotool if selected and on Linux
        if self.use_xdotool and current_os == "Linux":
            # Try xdotool first
            if self.type_with_xdotool(text):
                return
            # Fall back to clipboard if xdotool fails
            print("Falling back to clipboard method...", file=sys.stderr)
        
        # Default clipboard method
        try:
            pyperclip.copy(text)
            
            paste_key_char = 'v'  # Common paste character
            if current_os == "Darwin":  # macOS
                modifier_key = keyboard.Key.cmd
            elif current_os == "Windows" or current_os == "Linux":
                modifier_key = keyboard.Key.ctrl
            else:
                print(f"\nWarning: Unsupported OS '{current_os}' for auto-pasting. Text copied.", file=sys.stderr)
                return

            # Simulate paste
            with self.keyboard_controller.pressed(modifier_key):
                self.keyboard_controller.press(paste_key_char)
                self.keyboard_controller.release(paste_key_char)

        except pyperclip.PyperclipException as e:
            print(f"\nError copying to clipboard: {e}", file=sys.stderr)
            print("Ensure clipboard utilities are installed (e.g., xclip on Linux).")
        except Exception as e:
            print(f"\nUnexpected error during text output: {e}", file=sys.stderr)