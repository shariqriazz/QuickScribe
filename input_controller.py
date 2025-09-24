"""
Input Controller - Handles keyboard triggers and signal handling.
"""
import signal
from pynput import keyboard


class InputController:
    """Handles keyboard triggers and POSIX signal handling for recording control."""
    
    def __init__(self, trigger_key_name="alt_r", start_callback=None, stop_callback=None):
        self.trigger_key_name = trigger_key_name
        self.trigger_key = None
        self.start_callback = start_callback
        self.stop_callback = stop_callback
        self.is_recording = False
        self.listener = None
        
        # Setup trigger key
        self.setup_trigger_key(trigger_key_name)
        
        # Setup signal handlers
        self.setup_signal_handlers()
    
    def setup_trigger_key(self, key_name):
        """Sets up the trigger key based on the provided name."""
        if key_name is None or str(key_name).lower() in ("", "none", "disabled", "off"):
            self.trigger_key = None
            return True
        
        try:
            self.trigger_key = getattr(keyboard.Key, key_name)
        except AttributeError:
            if len(key_name) == 1:
                self.trigger_key = keyboard.KeyCode.from_char(key_name)
            else:
                print(f"Error: Invalid trigger key '{key_name}'. Use names like 'alt_r', 'ctrl_l', 'f1', or single characters.", file=sys.stderr)
                return False
        return True
    
    def setup_signal_handlers(self):
        """Setup POSIX signal handlers for SIGUSR1/SIGUSR2."""
        try:
            signal.signal(signal.SIGUSR1, self.handle_sigusr1)
            signal.signal(signal.SIGUSR2, self.handle_sigusr2)
        except Exception:
            pass  # Signal handling may not be available on all platforms
    
    def handle_sigusr1(self, signum, frame):
        """Handle SIGUSR1 signal to start recording."""
        try:
            if not self.is_recording and self.start_callback:
                self.start_callback()
                self.is_recording = True
        except Exception as e:
            print(f"\nError in SIGUSR1 handler: {e}", file=sys.stderr)
    
    def handle_sigusr2(self, signum, frame):
        """Handle SIGUSR2 signal to stop recording."""
        try:
            if self.is_recording and self.stop_callback:
                self.stop_callback()
                self.is_recording = False
        except Exception as e:
            print(f"\nError in SIGUSR2 handler: {e}", file=sys.stderr)
    
    def on_press(self, key):
        """Handle key press events."""
        try:
            if key == self.trigger_key and not self.is_recording:
                if self.start_callback:
                    self.start_callback()
                    self.is_recording = True
        except Exception as e:
            print(f"\nError in on_press: {e}", file=sys.stderr)
    
    def on_release(self, key):
        """Handle key release events."""
        try:
            if key == self.trigger_key and self.is_recording:
                if self.stop_callback:
                    self.stop_callback()
                    self.is_recording = False
            
            if key == keyboard.Key.esc:
                return False  # Stop listener
        except Exception as e:
            print(f"\nError in on_release: {e}", file=sys.stderr)
    
    def start_listener(self):
        """Start the keyboard listener if trigger key is configured."""
        if self.trigger_key is not None:
            self.listener = keyboard.Listener(on_press=self.on_press, on_release=self.on_release)
            self.listener.start()
            return self.listener
        return None
    
    def stop_listener(self):
        """Stop the keyboard listener."""
        if self.listener and self.listener.is_alive():
            self.listener.stop()
    
    def is_trigger_enabled(self):
        """Check if keyboard trigger is enabled."""
        return self.trigger_key is not None