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

# Output handling
from output_service import OutputService

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
        self.output_service = None
        self.input_controller = None
        self.provider = None
        
        # Configuration values
        self.provider_name = None
        self.model_id = None
        self.language = None
        self.sample_rate = DEFAULT_SAMPLE_RATE
        self.channels = DEFAULT_CHANNELS
        self.trigger_key_name = DEFAULT_TRIGGER_KEY
        self.use_xdotool = False
    
    def _get_conversation_context(self) -> ConversationContext:
        """Build conversation context from transcription service."""
        conversation_xml = ""
        compiled_text = ""
        if self.transcription_service.conversation_manager and self.transcription_service.conversation_manager.state.words:
            conversation_xml = self.transcription_service.conversation_manager.state.to_xml()
            compiled_text = self.transcription_service.conversation_manager.state.to_text()
        
        return ConversationContext(
            xml_markup=conversation_xml,
            compiled_text=compiled_text,
            sample_rate=self.sample_rate
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
                self.transcription_service.process_streaming_chunk(chunk_text, self.output_service.output_text_cross_platform)
            
            # Use unified provider interface - streaming only, no final callback
            self.provider.transcribe_audio(audio_np, context, streaming_callback, None)
            
        except Exception as e:
            print(f"\nError in process_audio: {e}", file=sys.stderr)
        finally:
            # Remind user how to record again
            if self.input_controller and self.input_controller.is_trigger_enabled():
                print(f"\nHold '{self.trigger_key_name}' to record...")
            else:
                print("\nKeyboard trigger disabled. Use SIGUSR1 to start and SIGUSR2 to stop.")
    
    def _initialize_services(self):
        """Initialize all service components."""
        self.transcription_service = TranscriptionService(use_xdotool=self.use_xdotool)
        self.output_service = OutputService(use_xdotool=self.use_xdotool)
        return True
    
    def _initialize_provider_client(self):
        """Initialize the provider client based on the selected provider."""
        try:
            self.provider = ProviderFactory.create_provider(self.provider_name, self.model_id, self.language)
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
            trigger_key_name=self.trigger_key_name,
            start_callback=start_recording_callback,
            stop_callback=stop_recording_callback
        )
        return True
    
    def initialize(self):
        """Initialize all components."""
        # Parse configuration
        if not self.config_manager.parse_configuration():
            return False
        self.config = self.config_manager.get_config()
        
        # Set configuration values
        self.provider_name = self.config['provider']
        self.model_id = self.config['model_id']
        self.language = self.config['language']
        self.sample_rate = self.config['sample_rate']
        self.channels = self.config['channels']
        self.trigger_key_name = self.config['trigger_key_name']
        self.use_xdotool = self.config['use_xdotool']
        
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
            sample_rate=self.sample_rate,
            channels=self.channels,
            dtype=DTYPE
        )
        
        return True
    
    def _display_configuration(self):
        """Display startup configuration."""
        print(f"\n--- Configuration ---")
        print(f"Provider:      {self.provider_name.upper()}")
        print(f"Model:         {self.model_id}")
        print(f"Trigger Key:   {'disabled' if not self.input_controller.is_trigger_enabled() else self.trigger_key_name}")
        print(f"Audio:         {self.sample_rate}Hz, {self.channels} channel(s)")
        print(f"Output Method: {'xdotool' if self.use_xdotool else 'clipboard paste'}")
        if self.provider_name == 'groq' and self.language:
            print(f"Language:      {self.language}")
        elif self.provider_name == 'gemini' and self.language:
            print(f"Language:      '{self.language}' (Note: Ignored by Gemini)")
        print("--------------------")
        print("Ensure Terminal/IDE has Microphone and Accessibility/Input Monitoring permissions.")
        if self.provider_name == 'gemini':
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
            print(f"\nHold '{self.trigger_key_name}' to record...")
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