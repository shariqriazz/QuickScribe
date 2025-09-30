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
        self.provider.transcribe_audio(audio_np, context, streaming_callback, None)

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

        # Send VOSK text to AI provider for processing
        self.provider.transcribe_text(text, context, streaming_callback, None)

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
        if not self._is_recording and self.audio_source:
            self._is_recording = True
            self.audio_source.start_recording()

    def stop_recording(self):
        """Stop recording and process result."""
        if self._is_recording and self.audio_source:
            self._is_recording = False
            result = self.audio_source.stop_recording()

            # Check for empty result and show prompt immediately
            if isinstance(result, AudioDataResult) and len(result.audio_data) == 0:
                self._show_recording_prompt()
                return

            # Process non-empty result in thread
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

    def handle_sigusr1(self, signum, frame):
        """Handle SIGUSR1 signal to start recording."""
        try:
            self.start_recording()
        except Exception as e:
            print(f"\nError in SIGUSR1 handler: {e}", file=sys.stderr)

    def handle_sigusr2(self, signum, frame):
        """Handle SIGUSR2 signal to stop recording."""
        try:
            self.stop_recording()
        except Exception as e:
            print(f"\nError in SIGUSR2 handler: {e}", file=sys.stderr)

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
        """Setup POSIX signal handlers for SIGUSR1/SIGUSR2."""
        try:
            signal.signal(signal.SIGUSR1, self.handle_sigusr1)
            signal.signal(signal.SIGUSR2, self.handle_sigusr2)
        except Exception:
            pass  # Signal handling may not be available on all platforms

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

    def _initialize_services(self):
        """Initialize all service components."""
        self.transcription_service = TranscriptionService(self.config)
        return True
    
    def _initialize_provider_client(self):
        """Initialize the provider client based on the selected provider."""
        try:
            self.provider = BaseProvider(
                self.config.model_id,
                self.config.language,
                self.config.api_key
            )

            # Provider should never be None now
            if self.provider is None:
                print("Error: No provider initialized", file=sys.stderr)
                return False

            # Apply performance configuration
            self.provider.enable_reasoning = self.config.enable_reasoning
            self.provider.thinking_budget = self.config.thinking_budget
            self.provider.temperature = self.config.temperature
            self.provider.max_tokens = self.config.max_tokens
            self.provider.top_p = self.config.top_p
            self.provider.debug_enabled = self.config.debug_enabled
            self.provider.litellm_debug = self.config.litellm_debug

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
    
    
    def initialize(self):
        """Initialize all components."""
        # Parse configuration
        if not self.config_manager.parse_configuration():
            return False
        self.config = self.config_manager
        
        # Initialize services
        if not self._initialize_services():
            return False
        
        # Initialize provider
        if not self._initialize_provider_client():
            return False

        # Initialize audio source based on --audio-source selection
        if self.config.audio_source in ['phoneme', 'wav2vec']:
            from wav2vec2_audio_source import Wav2Vec2AudioSource
            self.audio_source = Wav2Vec2AudioSource(
                self.config,
                model_path=self.config.wav2vec2_model_path,
                dtype='float32'  # Wav2Vec2 uses float32
            )
        elif self.config.audio_source == 'vosk':
            from vosk_audio_source import VoskAudioSource
            self.audio_source = VoskAudioSource(
                self.config,
                model_path=self.config.vosk_model_path,
                lgraph_path=self.config.vosk_lgraph_path,
                dtype=DTYPE
            )
        else:  # 'raw' or default
            self.audio_source = MicrophoneAudioSource(
                self.config,
                dtype=DTYPE
            )

        # Initialize and test audio source
        if not self.audio_source.initialize():
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
            print("\nKeyboard trigger disabled. Use SIGUSR1 to start and SIGUSR2 to stop.")

        listener = None
        try:
            # Audio device test is handled in audio_source.initialize()
            # No additional test needed here
            
            # Start input listener
            if self.is_trigger_enabled():
                listener = self.start_keyboard_listener()
                if listener:
                    listener.join()
            else:
                while True:
                    time.sleep(1)

        except KeyboardInterrupt:
            print("\nCtrl+C detected. Exiting.")
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
        if self.keyboard_listener and self.keyboard_listener.is_alive():
            self.keyboard_listener.stop()
        if self.audio_source:
            self.audio_source._cleanup()
        print("Exited.")