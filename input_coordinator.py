"""
Input Coordinator - Handles keyboard, POSIX signals, and system tray input.
"""
import sys
import signal
from pynput import keyboard
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon
from recording_session import RecordingSource
from ui import PosixSignalBridge
from lib.pr_log import pr_err, pr_debug, pr_warn, pr_notice, pr_info


class AbortRecording(Exception):
    """Abort recording due to additional key press during recording."""
    pass


class InputCoordinator:
    """Coordinates input from keyboard, POSIX signals, and system tray."""

    def __init__(self, config, recording_coordinator, processing_coordinator, app):
        self.config = config
        self.recording_coordinator = recording_coordinator
        self.processing_coordinator = processing_coordinator
        self.app = app

        self.trigger_key = None
        self.keyboard_listener = None
        self.qt_app = None
        self.signal_bridge = None
        self.system_tray = None

    def setup_trigger_key(self):
        """Sets up the trigger key based on configuration."""
        key_name = self.config.trigger_key_name
        if key_name is None or str(key_name).lower() in ("", "none", "disabled", "off"):
            self.trigger_key = None
            return True

        try:
            self.trigger_key = getattr(keyboard.Key, key_name)
        except AttributeError:
            if len(key_name) == 1:
                self.trigger_key = keyboard.KeyCode.from_char(key_name)
            else:
                pr_err(f"Invalid trigger key '{key_name}'. Use names like 'alt_r', 'ctrl_l', 'f1', or single characters.")
                return False
        return True

    def setup_signal_handlers(self):
        """Setup POSIX signal handlers via Qt bridge."""
        try:
            self.qt_app = QApplication.instance() or QApplication(sys.argv)
            pr_info("Qt application initialized")

            self.signal_bridge = PosixSignalBridge()
            self.signal_bridge.register_signal(signal.SIGUSR1, "mode_switch_1")
            self.signal_bridge.register_signal(signal.SIGUSR2, "mode_switch_2")
            self.signal_bridge.register_signal(signal.SIGHUP, "stop_recording")
            self.signal_bridge.register_signal(signal.SIGINT, "interrupt")
            self.signal_bridge.signal_received.connect(self._handle_signal_channel)
            pr_info("Signal bridge initialized")

        except Exception as e:
            pr_warn(f"Signal bridge initialization failed: {e}")
            import traceback
            traceback.print_exc()
            self.signal_bridge = None

        try:
            if not QSystemTrayIcon.isSystemTrayAvailable():
                pr_warn("System tray not available on this system")
                return

            from ui import SystemTrayUI, AppState
            self.system_tray = SystemTrayUI()
            self.system_tray.start_recording_requested.connect(self._start_recording_from_tray)
            self.system_tray.stop_recording_requested.connect(self._stop_recording_from_tray)
            self.system_tray.quit_requested.connect(self.qt_app.quit)
            self.system_tray.set_state(AppState.IDLE)
            pr_info("System tray initialized")

        except Exception as e:
            pr_warn(f"System tray initialization failed: {e}")
            import traceback
            traceback.print_exc()
            self.system_tray = None

    def start_keyboard_listener(self):
        """Start the keyboard listener if trigger key is configured."""
        if self.trigger_key is None:
            return None

        def safe_on_press(key):
            try:
                self.on_press(key)
            except AbortRecording:
                self.recording_coordinator.abort_recording()
                self.app._return_to_idle()
            except Exception as e:
                pr_err(f"Error in on_press: {e}")

        def safe_on_release(key):
            try:
                self.on_release(key)
            except Exception as e:
                pr_err(f"Error in on_release: {e}")

        self.keyboard_listener = keyboard.Listener(
            on_press=safe_on_press,
            on_release=safe_on_release
        )
        self.keyboard_listener.start()
        pr_debug("Keyboard listener started")
        return self.keyboard_listener

    def is_trigger_enabled(self):
        """Check if keyboard trigger is enabled."""
        return self.trigger_key is not None

    def on_press(self, key):
        """Handle key press events."""
        if key == self.trigger_key:
            pr_debug(f"Trigger key pressed, starting recording")
            self.recording_coordinator.start_recording(RecordingSource.KEYBOARD)
            return

        current_session = self.recording_coordinator.get_current_session()
        if not current_session:
            return

        if current_session.should_abort_on_keystroke():
            pr_debug("Non-trigger key pressed during keyboard recording, aborting")
            raise AbortRecording("Additional key pressed during recording")

    def on_release(self, key):
        """Handle key release events."""
        if key != self.trigger_key:
            return

        current_session = self.recording_coordinator.get_current_session()
        if not current_session:
            return

        pr_debug(f"Trigger key released, stopping recording")
        session, result, context = self.recording_coordinator.stop_recording()
        self.processing_coordinator.process_recording_result(session, result, context)

    def _handle_signal_channel(self, channel_name: str):
        """Handle signal received via bridge channel."""
        pr_notice(f"Signal channel received: {channel_name}")
        try:
            if channel_name == "mode_switch_1":
                pr_notice(f"Mode switch to: {self.config.sigusr1_mode}")
                self.recording_coordinator.start_signal_recording(self.config.sigusr1_mode)
            elif channel_name == "mode_switch_2":
                pr_notice(f"Mode switch to: {self.config.sigusr2_mode}")
                self.recording_coordinator.start_signal_recording(self.config.sigusr2_mode)
            elif channel_name == "stop_recording":
                pr_info("Stopping recording...")
                current_session = self.recording_coordinator.get_current_session()
                if not current_session:
                    return

                session, result, context = self.recording_coordinator.stop_recording()
                self.processing_coordinator.process_recording_result(session, result, context)
            elif channel_name == "interrupt":
                pr_notice("Ctrl+C detected. Exiting.")
                if self.qt_app:
                    self.qt_app.quit()
        except Exception as e:
            pr_err(f"Error handling signal channel '{channel_name}': {e}")
            import traceback
            traceback.print_exc()

    def _start_recording_from_tray(self):
        """Start recording from system tray."""
        self.recording_coordinator.start_recording(RecordingSource.SYSTEM_TRAY)

    def _stop_recording_from_tray(self):
        """Stop recording from system tray."""
        current_session = self.recording_coordinator.get_current_session()
        if not current_session:
            return

        session, result, context = self.recording_coordinator.stop_recording()
        self.processing_coordinator.process_recording_result(session, result, context)

    def cleanup(self):
        """Clean up input handling resources."""
        if self.system_tray:
            self.system_tray.cleanup()
        if self.signal_bridge:
            self.signal_bridge.cleanup()
        if self.keyboard_listener and self.keyboard_listener.is_alive():
            pr_debug("Stopping keyboard listener")
            self.keyboard_listener.stop()
