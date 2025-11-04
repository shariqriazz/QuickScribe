"""
Main dictation application using modular components.
"""
import time
import sys
import signal
import tempfile
import os
import io
import queue
import threading
import numpy as np
import soundfile as sf
from enum import Enum
from typing import Optional
from pynput import keyboard
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon
from PyQt6.QtCore import QTimer

# Configuration management
from config_manager import ConfigManager

# Audio handling
from microphone_audio_source import MicrophoneAudioSource
from audio_source import AudioResult, AudioDataResult, AudioTextResult

# Transcription processing
from transcription_service import TranscriptionService

# Output handling (removed - using direct xdotool via XMLStreamProcessor)

# Input handling - consolidated into DictationApp

# Provider
from providers.base_provider import BaseProvider
from providers.conversation_context import ConversationContext

# Qt UI components
from ui import PosixSignalBridge, SystemTrayUI, AppState

# Logging
from lib.pr_log import pr_emerg, pr_alert, pr_crit, pr_err, pr_warn, pr_notice, pr_info, pr_debug, get_streaming_handler

# Event queue for sequential processing
from lib.event_queue import EventQueue

# --- Constants ---
DTYPE = 'int16'
DEFAULT_TRIGGER_KEY = 'alt_r'
DEFAULT_SAMPLE_RATE = 16000
DEFAULT_CHANNELS = 1


class RecordingSource(Enum):
    """Source that initiated the recording."""
    KEYBOARD = "keyboard"
    SIGNAL = "signal"
    SYSTEM_TRAY = "system_tray"


class AbortRecording(Exception):
    """Abort recording due to additional key press during recording."""
    pass


class RecordingSession:
    """Encapsulates per-session state for two-queue architecture."""

    def __init__(self):
        self.chunk_queue = queue.Queue()
        self.chunks_complete = threading.Event()
        self.context = None


class DictationApp:
    """Main dictation application with provider abstraction."""

    def __init__(self):
        # Configuration
        self.config_manager = ConfigManager()
        self.config = None

        # Service components
        self.audio_source = None
        self.transcription_service = None
        self.provider = None

        # Input handling (moved from InputController)
        self.trigger_key = None
        self.keyboard_listener = None
        self._is_recording = False
        self._recording_source: Optional[RecordingSource] = None

        # Qt components
        self.qt_app = None
        self.signal_bridge = None
        self.system_tray = None
        self._app_state = AppState.IDLE

        # Session processing queue
        self.session_queue = None
    
    def _get_conversation_context(self) -> ConversationContext:
        """Build conversation context from XMLStreamProcessor state."""
        xml_markup = ""
        compiled_text = ""
        if self.transcription_service:
            xml_markup = self.transcription_service._build_xml_from_processor()
            compiled_text = self.transcription_service._build_current_text()

        return ConversationContext(
            xml_markup=xml_markup,
            compiled_text=compiled_text,
            sample_rate=self.config.sample_rate
        )

    def _record_to_session(self, result: AudioResult, session: RecordingSession):
        """Route audio result to model invocation based on type."""
        if not self.provider:
            session.chunks_complete.set()
            return

        try:
            if isinstance(result, AudioDataResult):
                self._invoke_model(session, audio_data=result.audio_data)
            elif isinstance(result, AudioTextResult):
                self._invoke_model(session, text_data=result.transcribed_text)
            else:
                pr_err(f"Unsupported audio result type: {type(result)}")
                session.chunks_complete.set()
        except Exception as e:
            pr_err(f"Error in record_to_session: {e}")
            session.chunks_complete.set()

    def _invoke_model(self, session: RecordingSession, audio_data=None, text_data=None):
        """Invoke model with streaming callback that collects chunks to session queue."""
        def streaming_callback(chunk_text):
            session.chunk_queue.put(chunk_text)

        try:
            self.provider.transcribe(
                session.context,
                audio_data=audio_data,
                text_data=text_data,
                streaming_callback=streaming_callback,
                final_callback=None
            )
        finally:
            session.chunks_complete.set()

    def _process_session_output(self, session: RecordingSession):
        """Process session chunks sequentially for keyboard output."""
        self.transcription_service.reset_streaming_state()

        while not session.chunks_complete.is_set() or not session.chunk_queue.empty():
            try:
                chunk = session.chunk_queue.get(timeout=0.1)
                self.transcription_service.process_streaming_chunk(chunk)
            except queue.Empty:
                continue
            except Exception as e:
                pr_err(f"Error processing chunk: {e}")

        self.transcription_service.complete_stream()

        final_text = self.transcription_service._build_current_text()
        if final_text:
            pr_info(f"{final_text}\n")
        else:
            pr_info("")

        if self.config.reset_state_each_response:
            self.transcription_service.reset_all_state()

    # Recording control - single point of truth
    def start_recording(self, source: RecordingSource):
        """Start recording if not already recording."""
        pr_debug(f"start_recording called: _is_recording={self._is_recording}, audio_source={self.audio_source is not None}, source={source.value}")
        if not self._is_recording and self.audio_source:
            self._is_recording = True
            self._recording_source = source
            pr_debug("Setting state to RECORDING")
            self._update_tray_state(AppState.RECORDING)
            pr_debug("Calling audio_source.start_recording()")
            self.audio_source.start_recording()
            pr_debug("Recording started")
        else:
            if self._is_recording:
                pr_debug("Already recording, ignoring")
            if not self.audio_source:
                pr_debug("No audio source available")

    def stop_recording(self):
        """Stop recording and process result."""
        if self._is_recording and self.audio_source:
            self._is_recording = False
            self._recording_source = None
            time.sleep(self.config.mic_release_delay / 1000.0)
            result = self.audio_source.stop_recording()

            # Check for empty result and show prompt immediately
            if isinstance(result, AudioDataResult) and len(result.audio_data) == 0:
                self._update_tray_state(AppState.IDLE)
                self._show_recording_prompt()
                return

            # Enqueue non-empty result for sequential processing
            self._update_tray_state(AppState.PROCESSING)
            session = RecordingSession()
            session.context = self._get_conversation_context()
            self.session_queue.enqueue(session)
            threading.Thread(target=self._record_to_session, args=(result, session), daemon=True).start()
            self._show_recording_prompt()

    def abort_recording(self):
        """Abort recording without processing audio."""
        if not self._is_recording:
            return
        if not self.audio_source:
            return

        self._is_recording = False
        self._recording_source = None
        self.audio_source.stop_recording()
        self._update_tray_state(AppState.IDLE)
        self._show_recording_prompt()

    # Input handling (moved from InputController)
    def on_press(self, key):
        """Handle key press events."""
        if key == self.trigger_key:
            pr_debug(f"Trigger key pressed, starting recording")
            self.start_recording(RecordingSource.KEYBOARD)
            return

        if not self._is_recording:
            return

        if self._recording_source == RecordingSource.KEYBOARD:
            pr_debug("Non-trigger key pressed during keyboard recording, aborting")
            raise AbortRecording("Additional key pressed during recording")

    def on_release(self, key):
        """Handle key release events."""
        if key != self.trigger_key:
            return

        pr_debug(f"Trigger key released, stopping recording")
        self.stop_recording()

    def _handle_signal_channel(self, channel_name: str):
        """Handle signal received via bridge channel."""
        pr_notice(f"Signal channel received: {channel_name}")
        try:
            if channel_name == "mode_switch_1":
                pr_notice(f"Mode switch to: {self.config.sigusr1_mode}")
                if self.transcription_service:
                    self.transcription_service._handle_mode_change(self.config.sigusr1_mode)
                pr_info("Starting recording...")
                self.start_recording(RecordingSource.SIGNAL)
            elif channel_name == "mode_switch_2":
                pr_notice(f"Mode switch to: {self.config.sigusr2_mode}")
                if self.transcription_service:
                    self.transcription_service._handle_mode_change(self.config.sigusr2_mode)
                pr_info("Starting recording...")
                self.start_recording(RecordingSource.SIGNAL)
            elif channel_name == "stop_recording":
                pr_info("Stopping recording...")
                self.stop_recording()
            elif channel_name == "interrupt":
                pr_notice("Ctrl+C detected. Exiting.")
                if self.qt_app:
                    self.qt_app.quit()
        except Exception as e:
            pr_err(f"Error handling signal channel '{channel_name}': {e}")
            import traceback
            traceback.print_exc()

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

            self.system_tray = SystemTrayUI()
            self.system_tray.start_recording_requested.connect(lambda: self.start_recording(RecordingSource.SYSTEM_TRAY))
            self.system_tray.stop_recording_requested.connect(self.stop_recording)
            self.system_tray.quit_requested.connect(self.qt_app.quit)
            self._update_tray_state(AppState.IDLE)
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
                self.abort_recording()
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

    def _show_recording_prompt(self):
        """Show appropriate recording prompt based on trigger configuration."""
        if self.trigger_key is not None:
            print(f"Hold '{self.config.trigger_key_name}' to record...")
        else:
            print("Keyboard trigger disabled. Use SIGUSR1 to start and SIGUSR2 to stop.")

    def _update_tray_state(self, new_state: AppState):
        """Update application state and notify system tray."""
        self._app_state = new_state
        if self.system_tray:
            self.system_tray.set_state(new_state)

    def _initialize_provider_client(self):
        """Initialize the provider client based on the selected provider."""
        try:
            # Pass audio_source to provider for instruction injection
            self.provider = BaseProvider(self.config, self.audio_source)

            # Provider should never be None now
            if self.provider is None:
                pr_err("No provider initialized")
                return False

            if self.provider.initialize():
                return True
            else:
                return False
        except ValueError as e:
            pr_err(f"{e}")
            return False
        except Exception as e:
            pr_err(f"Error initializing provider: {e}")
            return False

    def _initialize_services(self):
        """Initialize all service components."""
        self.transcription_service = TranscriptionService(self.config)

        self.session_queue = EventQueue(
            self._process_session_output,
            name="SessionProcessor"
        )
        self.session_queue.start()

        return True
    
    
    def initialize(self):
        """Initialize all components."""
        from lib.pr_log import set_log_level, PR_DEBUG, PR_INFO

        # Parse configuration
        if not self.config_manager.parse_configuration():
            return False
        self.config = self.config_manager

        # Set log level based on debug configuration
        if self.config.debug_enabled:
            set_log_level(PR_DEBUG)
        else:
            set_log_level(PR_INFO)

        # Initialize audio source based on --audio-source selection (BEFORE provider)
        if self.config.audio_source in ['transcribe', 'trans']:
            from transcription.factory import get_transcription_source
            try:
                self.audio_source = get_transcription_source(self.config)
            except RuntimeError as e:
                pr_err(f"{e}")
                return False
        else:
            self.audio_source = MicrophoneAudioSource(
                self.config,
                dtype=DTYPE
            )

        # Initialize and test audio source
        if not self.audio_source.initialize():
            return False

        # Initialize provider (AFTER audio_source, passing it as parameter)
        if not self._initialize_provider_client():
            return False

        # Initialize services (AFTER provider to access composer)
        if not self._initialize_services():
            return False

        # Setup input handling
        if not self.setup_trigger_key():
            return False

        self.setup_signal_handlers()
        
        return True
    
    def _display_configuration(self):
        """Display startup configuration."""
        pr_notice("--- Configuration ---")
        pr_info(f"Provider:      {self.config.provider.upper()}")
        pr_info(f"Model:         {self.config.model_id}")
        pr_info(f"Trigger Key:   {'disabled' if not self.is_trigger_enabled() else self.config.trigger_key_name}")
        pr_info(f"Audio:         {self.config.sample_rate}Hz, {self.config.channels} channel(s)")
        if sys.platform == 'darwin':
            output_method = 'macOS Core Graphics'
        elif sys.platform.startswith('linux') or sys.platform.startswith('freebsd'):
            output_method = 'xdotool'
        elif sys.platform == 'win32':
            output_method = 'Windows SendInput'
        else:
            output_method = 'none (test mode)'
        pr_info(f"Output Method: {output_method}")
        if self.config.provider == 'groq' and self.config.language:
            pr_info(f"Language:      {self.config.language}")
        elif self.config.provider == 'gemini' and self.config.language:
            pr_info(f"Language:      '{self.config.language}' (Note: Ignored by Gemini)")
        pr_notice("--------------------")
        pr_notice("Ensure Terminal/IDE has Microphone and Accessibility/Input Monitoring permissions.")
        if self.config.provider == 'gemini':
            pr_notice("Note: Gemini currently only transcribes English audio well.")
        pr_notice("Press Ctrl+C to exit.")
    
    def _display_xml_instructions(self):
        """Display XML instructions for the model (only when -DD or higher)."""
        if not self.config.litellm_debug:
            return

        pr_debug("="*60)
        pr_debug("SYSTEM INSTRUCTIONS FOR MODEL:")
        pr_debug("-" * 60)
        xml_instructions = self.provider.get_xml_instructions()
        pr_debug(xml_instructions)
        pr_debug("="*60)
    
    def run(self):
        """Main application loop."""
        # Initialize all components
        if not self.initialize():
            return 1
        
        # Display configuration
        self._display_configuration()
        
        # Display XML instructions
        self._display_xml_instructions()

        if self.is_trigger_enabled():
            print(f"Hold '{self.config.trigger_key_name}' to record...")
        else:
            pr_notice(f"Keyboard trigger disabled. Signal controls:")
            pr_info(f"  SIGUSR1 → {self.config.sigusr1_mode} mode + start recording")
            pr_info(f"  SIGUSR2 → {self.config.sigusr2_mode} mode + start recording")
            pr_info(f"  SIGHUP  → stop recording")

        listener = None
        try:
            # Audio device test is handled in audio_source.initialize()
            # No additional test needed here

            # Start input listener
            if self.is_trigger_enabled():
                listener = self.start_keyboard_listener()
                pr_debug(f"Keyboard listener started")

            # Run Qt event loop (handles both signals and events)
            if self.qt_app:
                pr_debug(f"Starting Qt event loop (qt_app exists, listener={'exists' if listener else 'None'})")
                self.qt_app.exec()
            elif listener:
                pr_debug("No Qt app, running keyboard listener loop")
                listener.join()
            else:
                pr_debug("No Qt app, no listener, running sleep loop")
                while True:
                    time.sleep(1)

        except Exception as e:
            pr_err(f"An unexpected error occurred in main execution: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.cleanup()
            return 0
    
    def cleanup(self):
        """Clean up resources."""
        pr_info("Cleaning up...")
        if self.session_queue:
            self.session_queue.shutdown()
        if self.system_tray:
            self.system_tray.cleanup()
        if self.signal_bridge:
            self.signal_bridge.cleanup()
        if self.keyboard_listener and self.keyboard_listener.is_alive():
            pr_debug("Stopping keyboard listener")
            self.keyboard_listener.stop()
        if self.audio_source:
            self.audio_source._cleanup()
        pr_info("Exited.")