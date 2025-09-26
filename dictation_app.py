"""
Main dictation application using modular components.
"""
import time
import sys
import tempfile
import os
import io
import numpy as np
import soundfile as sf

# Configuration management
from config_manager import ConfigManager

# Audio handling
from audio_handler import AudioHandler

# Transcription processing
from transcription_service import TranscriptionService

# Output handling (removed - using direct xdotool via XMLStreamProcessor)

# Input handling
from input_controller import InputController

# Provider factory
from providers.provider_factory import ProviderFactory
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
        self.audio_handler = None
        self.transcription_service = None
        self.input_controller = None
        self.provider = None
    
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
    
    def _process_audio(self, audio_np):
        """Generic audio processing without provider conditionals."""
        if not self.provider or not self.transcription_service:
            return
        
        try:
            self.transcription_service.reset_streaming_state()
            
            # Get conversation context
            context = self._get_conversation_context()
            
            # Define callbacks
            def streaming_callback(chunk_text):
                print(chunk_text, end='', flush=True)
                self.transcription_service.process_streaming_chunk(chunk_text)
            
            # Use unified provider interface - streaming only, no final callback
            self.provider.transcribe_audio(audio_np, context, streaming_callback, None)
            
            # Show final clean state when streaming is complete
            final_text = self.transcription_service._build_current_text()
            if final_text:
                print(f"\n{final_text}")  # New line and show final result
            else:
                print()  # Just add a newline
            
        except Exception as e:
            print(f"\nError in process_audio: {e}", file=sys.stderr)
        finally:
            # Remind user how to record again
            if self.input_controller and self.input_controller.is_trigger_enabled():
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
            self.provider = ProviderFactory.create_provider(self.config.provider, self.config.model_id, self.config.language)
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
    
    def _initialize_input_controller(self):
        """Initialize the input controller with callbacks."""
        def start_recording_callback():
            if self.audio_handler:
                self.audio_handler.start_recording()
        
        def stop_recording_callback():
            if self.audio_handler:
                self.audio_handler.stop_recording_and_process(self._process_audio)
        
        self.input_controller = InputController(
            trigger_key_name=self.config.trigger_key_name,
            start_callback=start_recording_callback,
            stop_callback=stop_recording_callback
        )
        return True
    
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
        
        # Initialize input controller
        if not self._initialize_input_controller():
            return False
        
        # Initialize audio handler
        self.audio_handler = AudioHandler(
            self.config,
            dtype=DTYPE
        )
        
        return True
    
    def _display_configuration(self):
        """Display startup configuration."""
        print(f"\n--- Configuration ---")
        print(f"Provider:      {self.config.provider.upper()}")
        print(f"Model:         {self.config.model_id}")
        print(f"Trigger Key:   {'disabled' if not self.input_controller.is_trigger_enabled() else self.config.trigger_key_name}")
        print(f"Audio:         {self.config.sample_rate}Hz, {self.config.channels} channel(s)")
        print(f"Output Method: {'xdotool' if self.config.use_xdotool else 'none (test mode)'}")
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
        
        if self.input_controller.is_trigger_enabled():
            print(f"\nHold '{self.config.trigger_key_name}' to record...")
        else:
            print("\nKeyboard trigger disabled. Use SIGUSR1 to start and SIGUSR2 to stop.")

        listener = None
        try:
            # Test audio
            if not self.audio_handler.test_audio_device():
                print("\nFATAL: Audio device error", file=sys.stderr)
                return 1
            
            # Start input listener
            if self.input_controller.is_trigger_enabled():
                listener = self.input_controller.start_listener()
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
        if self.input_controller:
            self.input_controller.stop_listener()
        if self.audio_handler:
            self.audio_handler.cleanup()
        print("Exited.")