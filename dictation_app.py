"""
Main dictation application using modular components.
"""
import time
import sys
import signal
import tempfile
import os
import io
import threading
import numpy as np
import soundfile as sf
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

# --- Constants ---
DTYPE = 'int16'
DEFAULT_TRIGGER_KEY = 'alt_r'
DEFAULT_SAMPLE_RATE = 16000
DEFAULT_CHANNELS = 1


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

        # Qt components
        self.qt_app = None
        self.signal_bridge = None
        self.system_tray = None
        self._app_state = AppState.IDLE
    
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
    
    def _process_audio_result(self, result: AudioResult):
        """Process audio result from any audio source."""
        if not self.transcription_service:
            return

        # Provider is required for both audio and text processing
        if not self.provider:
            return

        try:
            # Handle different result types
            if isinstance(result, AudioDataResult):
                self._process_audio_data(result.audio_data)
            elif isinstance(result, AudioTextResult):
                # Handle pre-transcribed text from VOSK
                self._process_transcribed_text(result.transcribed_text)
            else:
                print(f"Unsupported audio result type: {type(result)}", file=sys.stderr)
        except Exception as e:
            print(f"\nError in process_audio_result: {e}", file=sys.stderr)

    def _process_audio_data(self, audio_np):
        """Process raw audio data using provider."""
        if not self.provider:
            print("Error: No provider available for audio transcription", file=sys.stderr)
            return

        self.transcription_service.reset_streaming_state()

        # Get conversation context
        context = self._get_conversation_context()

        # Define callbacks
        def streaming_callback(chunk_text):
            print(chunk_text, end='', flush=True)
            self.transcription_service.process_streaming_chunk(chunk_text)

        # Use unified provider interface - streaming only, no final callback
        self.provider.transcribe(context, audio_data=audio_np,
                                streaming_callback=streaming_callback, final_callback=None)

        # CRITICAL: Complete the stream to handle any remaining content
        self.transcription_service.complete_stream()

        # Show final clean state when streaming is complete
        final_text = self.transcription_service._build_current_text()
        if final_text:
            print(f"\n{final_text}")  # New line and show final result
        else:
            print()  # Just add a newline

    def _process_transcribed_text(self, text):
        """Process pre-transcribed text from VOSK through AI provider."""
        if not text or not text.strip():
            return

        # Reset streaming state for fresh processing
        self.transcription_service.reset_streaming_state()

        # Get conversation context
        context = self._get_conversation_context()

        # Define callbacks (same as audio processing)
        def streaming_callback(chunk_text):
            print(chunk_text, end='', flush=True)
            self.transcription_service.process_streaming_chunk(chunk_text)

        # Send text to AI provider for processing
        self.provider.transcribe(context, text_data=text,
                                streaming_callback=streaming_callback, final_callback=None)

        # CRITICAL: Complete the stream to handle any remaining content
        self.transcription_service.complete_stream()

        # Show final clean state when streaming is complete
        final_text = self.transcription_service._build_current_text()
        if final_text:
            print(f"\n{final_text}")  # New line and show final result
        else:
            print()  # Just add a newline

    # Recording control - single point of truth
    def start_recording(self):
        """Start recording if not already recording."""
        print(f"start_recording called: _is_recording={self._is_recording}, audio_source={self.audio_source is not None}")
        if not self._is_recording and self.audio_source:
            self._is_recording = True
            print("Setting state to RECORDING")
            self._update_tray_state(AppState.RECORDING)
            print("Calling audio_source.start_recording()")
            self.audio_source.start_recording()
            print("Recording started")
        else:
            if self._is_recording:
                print("Already recording, ignoring")
            if not self.audio_source:
                print("No audio source available")

    def stop_recording(self):
        """Stop recording and process result."""
        if self._is_recording and self.audio_source:
            self._is_recording = False
            time.sleep(self.config.mic_release_delay / 1000.0)
            result = self.audio_source.stop_recording()

            # Check for empty result and show prompt immediately
            if isinstance(result, AudioDataResult) and len(result.audio_data) == 0:
                self._update_tray_state(AppState.IDLE)
                self._show_recording_prompt()
                return

            # Process non-empty result in thread
            self._update_tray_state(AppState.PROCESSING)
            threading.Thread(
                target=self._process_audio_result_and_prompt,
                args=(result,),
                daemon=True
            ).start()

    def _process_audio_result_and_prompt(self, result):
        """Process result and always show prompt after."""
        try:
            self._process_audio_result(result)
        finally:
            self._update_tray_state(AppState.IDLE)
            self._show_recording_prompt()

    # Input handling (moved from InputController)
    def on_press(self, key):
        """Handle key press events."""
        try:
            if key == self.trigger_key:
                self.start_recording()
        except Exception as e:
            print(f"\nError in on_press: {e}", file=sys.stderr)

    def on_release(self, key):
        """Handle key release events."""
        try:
            if key == self.trigger_key:
                self.stop_recording()
            elif key == keyboard.Key.esc:
                return False  # Stop listener
        except Exception as e:
            print(f"\nError in on_release: {e}", file=sys.stderr)

    def _handle_signal_channel(self, channel_name: str):
        """Handle signal received via bridge channel."""
        print(f"\nSignal channel received: {channel_name}")
        try:
            if channel_name == "mode_switch_1":
                print(f"Mode switch to: {self.config.sigusr1_mode}")
                if self.transcription_service:
                    self.transcription_service._handle_mode_change(self.config.sigusr1_mode)
                print("Starting recording...")
                self.start_recording()
            elif channel_name == "mode_switch_2":
                print(f"Mode switch to: {self.config.sigusr2_mode}")
                if self.transcription_service:
                    self.transcription_service._handle_mode_change(self.config.sigusr2_mode)
                print("Starting recording...")
                self.start_recording()
            elif channel_name == "stop_recording":
                print("Stopping recording...")
                self.stop_recording()
            elif channel_name == "interrupt":
                print("\nCtrl+C detected. Exiting.")
                if self.qt_app:
                    self.qt_app.quit()
        except Exception as e:
            print(f"\nError handling signal channel '{channel_name}': {e}", file=sys.stderr)
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
                print(f"Error: Invalid trigger key '{key_name}'. Use names like 'alt_r', 'ctrl_l', 'f1', or single characters.", file=sys.stderr)
                return False
        return True

    def setup_signal_handlers(self):
        """Setup POSIX signal handlers via Qt bridge."""
        try:
            self.qt_app = QApplication.instance() or QApplication(sys.argv)
            print("Qt application initialized")

            self.signal_bridge = PosixSignalBridge()
            self.signal_bridge.register_signal(signal.SIGUSR1, "mode_switch_1")
            self.signal_bridge.register_signal(signal.SIGUSR2, "mode_switch_2")
            self.signal_bridge.register_signal(signal.SIGHUP, "stop_recording")
            self.signal_bridge.register_signal(signal.SIGINT, "interrupt")
            self.signal_bridge.signal_received.connect(self._handle_signal_channel)
            print("Signal bridge initialized")

        except Exception as e:
            print(f"Warning: Signal bridge initialization failed: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            self.signal_bridge = None

        try:
            if not QSystemTrayIcon.isSystemTrayAvailable():
                print("Warning: System tray not available on this system", file=sys.stderr)
                return

            self.system_tray = SystemTrayUI()
            self.system_tray.start_recording_requested.connect(self.start_recording)
            self.system_tray.stop_recording_requested.connect(self.stop_recording)
            self.system_tray.quit_requested.connect(self.qt_app.quit)
            self._update_tray_state(AppState.IDLE)
            print("System tray initialized")

        except Exception as e:
            print(f"Warning: System tray initialization failed: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            self.system_tray = None

    def start_keyboard_listener(self):
        """Start the keyboard listener if trigger key is configured."""
        if self.trigger_key is not None:
            self.keyboard_listener = keyboard.Listener(
                on_press=self.on_press,
                on_release=self.on_release
            )
            self.keyboard_listener.start()
            return self.keyboard_listener
        return None

    def is_trigger_enabled(self):
        """Check if keyboard trigger is enabled."""
        return self.trigger_key is not None

    def _show_recording_prompt(self):
        """Show appropriate recording prompt based on trigger configuration."""
        if self.trigger_key is not None:
            print(f"\nHold '{self.config.trigger_key_name}' to record...")
        else:
            print("\nKeyboard trigger disabled. Use SIGUSR1 to start and SIGUSR2 to stop.")

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
                print("Error: No provider initialized", file=sys.stderr)
                return False

            if self.provider.initialize():
                return True
            else:
                return False
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return False
        except Exception as e:
            print(f"Error initializing provider: {e}", file=sys.stderr)
            return False

    def _initialize_services(self):
        """Initialize all service components."""
        self.transcription_service = TranscriptionService(self.config)
        return True
    
    
    def initialize(self):
        """Initialize all components."""
        # Parse configuration
        if not self.config_manager.parse_configuration():
            return False
        self.config = self.config_manager

        # Initialize audio source based on --audio-source selection (BEFORE provider)
        if self.config.audio_source in ['transcribe', 'trans']:
            from transcription.factory import get_transcription_source
            self.audio_source = get_transcription_source(self.config)
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
        print(f"\n--- Configuration ---")
        print(f"Provider:      {self.config.provider.upper()}")
        print(f"Model:         {self.config.model_id}")
        print(f"Trigger Key:   {'disabled' if not self.is_trigger_enabled() else self.config.trigger_key_name}")
        print(f"Audio:         {self.config.sample_rate}Hz, {self.config.channels} channel(s)")
        if sys.platform == 'darwin':
            output_method = 'macOS Core Graphics'
        elif sys.platform.startswith('linux') or sys.platform.startswith('freebsd'):
            output_method = 'xdotool'
        elif sys.platform == 'win32':
            output_method = 'Windows SendInput'
        else:
            output_method = 'none (test mode)'
        print(f"Output Method: {output_method}")
        if self.config.provider == 'groq' and self.config.language:
            print(f"Language:      {self.config.language}")
        elif self.config.provider == 'gemini' and self.config.language:
            print(f"Language:      '{self.config.language}' (Note: Ignored by Gemini)")
        print("--------------------")
        print("Ensure Terminal/IDE has Microphone and Accessibility/Input Monitoring permissions.")
        if self.config.provider == 'gemini':
            print("Note: Gemini currently only transcribes English audio well.")
        print("Press Ctrl+C to exit.")
    
    def _display_xml_instructions(self):
        """Display XML instructions for the model."""
        print("\n" + "="*60)
        print("SYSTEM INSTRUCTIONS FOR MODEL:")
        print("-" * 60)
        xml_instructions = self.provider.get_xml_instructions()
        print(xml_instructions)
        print("="*60)
    
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
            print(f"\nHold '{self.config.trigger_key_name}' to record...")
        else:
            print(f"\nKeyboard trigger disabled. Signal controls:")
            print(f"  SIGUSR1 → {self.config.sigusr1_mode} mode + start recording")
            print(f"  SIGUSR2 → {self.config.sigusr2_mode} mode + start recording")
            print(f"  SIGHUP  → stop recording")

        listener = None
        try:
            # Audio device test is handled in audio_source.initialize()
            # No additional test needed here

            # Start input listener
            if self.is_trigger_enabled():
                listener = self.start_keyboard_listener()
                print(f"Keyboard listener started")

            # Run Qt event loop (handles both signals and events)
            if self.qt_app:
                print(f"Starting Qt event loop (qt_app exists, listener={'exists' if listener else 'None'})")
                self.qt_app.exec()
            elif listener:
                print("No Qt app, running keyboard listener loop")
                listener.join()
            else:
                print("No Qt app, no listener, running sleep loop")
                while True:
                    time.sleep(1)

        except Exception as e:
            print(f"\nAn unexpected error occurred in main execution: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
        finally:
            self.cleanup()
            return 0
    
    def cleanup(self):
        """Clean up resources."""
        print("\nCleaning up...")
        if self.system_tray:
            self.system_tray.cleanup()
        if self.signal_bridge:
            self.signal_bridge.cleanup()
        if self.keyboard_listener and self.keyboard_listener.is_alive():
            self.keyboard_listener.stop()
        if self.audio_source:
            self.audio_source._cleanup()
        print("Exited.")