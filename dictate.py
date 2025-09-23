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

# --- Constants ---
DTYPE = 'int16'
DEFAULT_TRIGGER_KEY = 'alt_r'
DEFAULT_SAMPLE_RATE = 16000
DEFAULT_CHANNELS = 1

# --- Global Variables ---
audio_handler = None
transcription_service = None
output_service = None
input_controller = None
provider = None

# Configuration
PROVIDER = None
MODEL_ID = None
LANGUAGE = None
SAMPLE_RATE = DEFAULT_SAMPLE_RATE
CHANNELS = DEFAULT_CHANNELS
TRIGGER_KEY_NAME = DEFAULT_TRIGGER_KEY
USE_XDOTOOL = False

# --- Helper Functions ---

def initialize_services():
    """Initialize all service components."""
    global transcription_service, output_service
    transcription_service = TranscriptionService(use_xdotool=USE_XDOTOOL)
    output_service = OutputService(use_xdotool=USE_XDOTOOL)

def initialize_provider_client():
    """Initializes the provider client based on the selected PROVIDER."""
    global provider
    
    try:
        provider = ProviderFactory.create_provider(PROVIDER, MODEL_ID, LANGUAGE)
        if provider.initialize():
            return True
        else:
            return False
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"Error initializing provider: {e}", file=sys.stderr)
        return False

def initialize_input_controller():
    """Initialize the input controller with callbacks."""
    global input_controller
    
    def start_recording_callback():
        if audio_handler:
            audio_handler.start_recording()
    
    def stop_recording_callback():
        if audio_handler:
            audio_handler.stop_recording_and_process(process_audio_callback)
    
    input_controller = InputController(
        trigger_key_name=TRIGGER_KEY_NAME,
        start_callback=start_recording_callback,
        stop_callback=stop_recording_callback
    )
    return True

def process_audio_callback(audio_np):
    """Process audio through the provider and transcription service."""
    if not provider or not transcription_service:
        return
    
    tmp_filename = None
    
    try:
        transcription_service.reset_streaming_state()
        
        if PROVIDER == 'groq':
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
                tmp_filename = tmp_file.name
                sf.write(tmp_filename, audio_np, SAMPLE_RATE)

            with open(tmp_filename, "rb") as file_for_groq:
                try:
                    # Get conversation context
                    conversation_xml = ""
                    compiled_text = ""
                    if transcription_service.conversation_manager and transcription_service.conversation_manager.state.words:
                        conversation_xml = transcription_service.conversation_manager.state.to_xml()
                        compiled_text = transcription_service.conversation_manager.state.to_text()
                    
                    # Display conversation flow
                    print("\n" + "="*60)
                    print("SENDING TO MODEL:")
                    print("[conversation context being sent]")
                    print(f"XML markup: {conversation_xml if conversation_xml else '[no conversation history]'}")
                    print(f"Rendered text: {compiled_text if compiled_text else '[empty]'}")
                    print(f"Audio file: {os.path.basename(tmp_filename)}")
                    print("-" * 60)
                    
                    # Transcribe with provider
                    result = provider.transcribe_audio_file(tmp_filename, conversation_xml, compiled_text)
                    if result:
                        # Process final result
                        transcription_service.process_xml_transcription(result, output_service.output_text_cross_platform)
                        
                except Exception as e:
                    print(f"\nError during Groq transcription: {e}", file=sys.stderr)

        elif PROVIDER == 'gemini':
            wav_bytes_io = io.BytesIO()
            sf.write(wav_bytes_io, audio_np, SAMPLE_RATE, format='WAV', subtype='PCM_16')
            wav_bytes = wav_bytes_io.getvalue()
            wav_bytes_io.close()

            if len(wav_bytes) > 18 * 1024 * 1024:
                print("\nWarning: Audio data >18MB, may fail inline Gemini request.")

            try:
                # Get conversation context
                conversation_xml = ""
                compiled_text = ""
                if transcription_service.conversation_manager and transcription_service.conversation_manager.state.words:
                    conversation_xml = transcription_service.conversation_manager.state.to_xml()
                    compiled_text = transcription_service.conversation_manager.state.to_text()
                
                # Display conversation flow
                print("\n" + "="*60)
                print("SENDING TO MODEL:")
                print("[conversation context being sent]")
                print(f"XML markup: {conversation_xml if conversation_xml else '[no conversation history]'}")
                print(f"Rendered text: {compiled_text if compiled_text else '[empty]'}")
                print(f"Audio file: [audio_data.wav]")
                print("-" * 60)
                
                # Transcribe with streaming
                def streaming_callback(chunk_text):
                    print(chunk_text, end='', flush=True)
                    transcription_service.process_streaming_chunk(chunk_text, output_service.output_text_cross_platform)
                
                def final_callback(full_text):
                    print()  # New line after streaming
                    if full_text:
                        transcription_service.process_xml_transcription(full_text, output_service.output_text_cross_platform)
                
                print("\nRECEIVED FROM MODEL (streaming):")
                provider.transcribe_audio_bytes(wav_bytes, conversation_xml, compiled_text, 
                                               streaming_callback, final_callback)
                
            except Exception as e:
                print(f"\nError during Gemini transcription: {e}", file=sys.stderr)

    except Exception as e:
        print(f"\nError in process_audio: {e}", file=sys.stderr)
    finally:
        if tmp_filename and os.path.exists(tmp_filename):
            try:
                os.remove(tmp_filename)
            except OSError as e:
                print(f"\nError deleting temp file {tmp_filename}: {e}", file=sys.stderr)
        
        # Remind user how to record again
        if input_controller and input_controller.is_trigger_enabled():
            print(f"\nHold '{TRIGGER_KEY_NAME}' to record...")
        else:
            print("\nKeyboard trigger disabled. Use SIGUSR1 to start and SIGUSR2 to stop.")

# --- Main Execution ---
if __name__ == "__main__":
    # Initialize configuration
    config_manager = ConfigManager()
    if not config_manager.parse_configuration():
        sys.exit(1)
    config = config_manager.get_config()
    
    # Set global variables from config
    PROVIDER = config['provider']
    MODEL_ID = config['model_id'] 
    LANGUAGE = config['language']
    SAMPLE_RATE = config['sample_rate']
    CHANNELS = config['channels']
    TRIGGER_KEY_NAME = config['trigger_key_name']
    USE_XDOTOOL = config['use_xdotool']
    
    # Initialize services
    initialize_services()
    
    # Initialize provider
    if not initialize_provider_client():
        sys.exit(1)
    
    # Initialize input controller
    if not initialize_input_controller():
        sys.exit(1)
    
    # Initialize audio handler
    audio_handler = AudioHandler(
        sample_rate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype=DTYPE
    )
    
    # Print configuration
    print(f"\n--- Configuration ---")
    print(f"Provider:      {PROVIDER.upper()}")
    print(f"Model:         {MODEL_ID}")
    print(f"Trigger Key:   {'disabled' if not input_controller.is_trigger_enabled() else TRIGGER_KEY_NAME}")
    print(f"Audio:         {SAMPLE_RATE}Hz, {CHANNELS} channel(s)")
    print(f"Output Method: {'xdotool' if USE_XDOTOOL else 'clipboard paste'}")
    if PROVIDER == 'groq' and LANGUAGE:
        print(f"Language:      {LANGUAGE}")
    elif PROVIDER == 'gemini' and LANGUAGE:
        print(f"Language:      '{LANGUAGE}' (Note: Ignored by Gemini)")
    print("--------------------")
    print("Ensure Terminal/IDE has Microphone and Accessibility/Input Monitoring permissions.")
    if PROVIDER == 'gemini':
        print("Note: Gemini currently only transcribes English audio well.")
    print("Press Ctrl+C to exit.")
    
    # Display XML instructions
    print("\n" + "="*60)
    print("SYSTEM INSTRUCTIONS FOR MODEL:")
    print("-" * 60)
    xml_instructions = provider.get_xml_instructions()
    print(xml_instructions)
    print("="*60)
    
    if input_controller.is_trigger_enabled():
        print(f"\nHold '{TRIGGER_KEY_NAME}' to record...")
    else:
        print("\nKeyboard trigger disabled. Use SIGUSR1 to start and SIGUSR2 to stop.")

    listener = None
    try:
        # Test audio
        if not audio_handler.test_audio_device():
            print("\nFATAL: Audio device error", file=sys.stderr)
            sys.exit(1)
        print("Audio device check successful.")
        
        # Start input listener
        if input_controller.is_trigger_enabled():
            listener = input_controller.start_listener()
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
        print("\nCleaning up...")
        if input_controller:
            input_controller.stop_listener()
        if audio_handler:
            audio_handler.cleanup()
        print("Exited.")