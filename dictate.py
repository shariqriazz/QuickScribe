import sounddevice as sd
import soundfile as sf
import numpy as np
import threading
import queue
import tempfile
import io
import os
import subprocess
import sys
import argparse
import platform  # To detect OS for key combinations
import shlex  # For safe shell argument escaping
import re  # For regex processing
from pynput import keyboard
from dotenv import load_dotenv

# Import XML processing modules
from lib.word_stream import WordStreamParser, DictationWord
from lib.diff_engine import DiffEngine
from lib.output_manager import OutputManager

# Cross-platform typing/pasting libraries
try:
    import pyperclip
except ImportError:
    print("Error: pyperclip library not found. Please install it: pip install pyperclip")
    sys.exit(1)

# XML word processing modules
from lib.word_stream import WordStreamParser, DictationWord
from lib.diff_engine import DiffEngine
from lib.output_manager import OutputManager, XdotoolError

# --- Constants ---
DTYPE = 'int16' # Data type for recording
DEFAULT_TRIGGER_KEY = 'alt_r'
DEFAULT_SAMPLE_RATE = 16000
DEFAULT_CHANNELS = 1

# --- Global Variables ---
is_recording = False
audio_queue = queue.Queue()
recording_stream = None
keyboard_controller = keyboard.Controller()
# These will be set later by args or interactive mode
PROVIDER = None
MODEL_ID = None
LANGUAGE = None
SAMPLE_RATE = DEFAULT_SAMPLE_RATE
CHANNELS = DEFAULT_CHANNELS
TRIGGER_KEY_NAME = DEFAULT_TRIGGER_KEY
TRIGGER_KEY = None
# Provider specific clients/models
groq_client = None
gemini_model = None
api_key = None # To store the loaded key
# Output method
USE_XDOTOOL = False # Default to copy-paste method
LAST_TYPED_TEXT = "" # Track the last text that was typed for editing
CONVERSATION_HISTORY = [] # Track conversation context for continuous dialogue (memory only)

# XML processing components
word_parser = None
diff_engine = None
output_manager = None
current_words = [] # Track current word state for diff processing

# --- Helper Functions ---

def load_models_from_file(filename):
    """Loads model names from a text file."""
    try:
        script_dir = os.path.dirname(__file__) # Get directory of the current script
        filepath = os.path.join(script_dir, filename)
        with open(filepath, 'r') as f:
            models = [line.strip() for line in f if line.strip()]
        return models
    except FileNotFoundError:
        print(f"Error: Model file '{filename}' not found in '{script_dir}'.", file=sys.stderr)
        return []
    except Exception as e:
        print(f"Error reading model file '{filename}': {e}", file=sys.stderr)
        return []

def select_from_list(options, prompt):
    """Prompts user to select an option from a list."""
    if not options:
        return None
    print(prompt)
    for i, option in enumerate(options):
        print(f"{i + 1}. {option}")
    while True:
        try:
            choice = input(f"Enter number (1-{len(options)}): ")
            index = int(choice) - 1
            if 0 <= index < len(options):
                return options[index]
            else:
                print("Invalid choice.")
        except ValueError:
            print("Invalid input. Please enter a number.")
        except EOFError:
            print("\nSelection cancelled.")
            return None # Handle Ctrl+D

def initialize_xml_components():
    """Initialize the XML processing components."""
    global word_parser, diff_engine, output_manager
    word_parser = WordStreamParser()
    diff_engine = DiffEngine()
    output_manager = OutputManager()

def initialize_provider_client():
    """Initializes the API client based on the selected PROVIDER."""
    global groq_client, gemini_model, api_key # Allow modification

    if PROVIDER == 'groq':
        try:
            from groq import Groq, GroqError
        except ImportError:
            print("Error: groq library not found. Please install it: pip install groq", file=sys.stderr)
            return False
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            print("Error: GROQ_API_KEY not found in environment variables or .env file.", file=sys.stderr)
            return False
        try:
            groq_client = Groq(api_key=api_key)
            print("Groq client initialized.")
            return True
        except Exception as e:
            print(f"Error initializing Groq client: {e}", file=sys.stderr)
            return False

    elif PROVIDER == 'gemini':
        try:
            import google.generativeai as genai
            # Import specific exception type
            from google.api_core import exceptions as google_exceptions
        except ImportError:
            print("Error: google-generativeai library not found. Please install it: pip install google-generativeai", file=sys.stderr)
            return False
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            print("Error: GOOGLE_API_KEY not found in environment variables or .env file.", file=sys.stderr)
            return False
        try:
            genai.configure(api_key=api_key)
            gemini_model = genai.GenerativeModel(MODEL_ID)
            print("Gemini client initialized.")
            return True
        # Catch specific Google exceptions if needed during init, though less likely here
        except Exception as e:
            print(f"Error configuring or creating Gemini model instance ({MODEL_ID}): {e}", file=sys.stderr)
            return False
    else:
        print("Error: No valid provider selected.", file=sys.stderr)
        return False

def setup_trigger_key(key_name):
    """Sets up the trigger key based on the provided name."""
    global TRIGGER_KEY
    try:
        TRIGGER_KEY = getattr(keyboard.Key, key_name)
        # print(f"Using special key: {key_name}") # Less verbose
    except AttributeError:
        if len(key_name) == 1:
            TRIGGER_KEY = keyboard.KeyCode.from_char(key_name)
            # print(f"Using character key: '{key_name}'") # Less verbose
        else:
            print(f"Error: Invalid trigger key '{key_name}'. Use names like 'alt_r', 'ctrl_l', 'f1', or single characters.", file=sys.stderr)
            return False
    return True

def process_xml_transcription(text):
    """Process XML transcription text using the word processing pipeline."""
    global CONVERSATION_HISTORY, current_words, word_parser, diff_engine, output_manager
    
    try:
        # Check for conversation tags first
        conversation_pattern = re.compile(r'<conversation>(.*?)</conversation>', re.DOTALL)
        conversation_matches = conversation_pattern.findall(text)
        
        # Process conversation content
        for conversation_content in conversation_matches:
            content = conversation_content.strip()
            if content:
                # Process commands in conversation content
                cleaned_content = detect_and_execute_commands(content)
                if cleaned_content.strip():
                    CONVERSATION_HISTORY.append(cleaned_content)
                    # Keep only last 10 exchanges
                    if len(CONVERSATION_HISTORY) > 10:
                        CONVERSATION_HISTORY.pop(0)
        
        # Remove conversation tags from text before processing words
        text_without_conversation = conversation_pattern.sub('', text)
        
        # Parse XML to extract words
        newly_completed_words = word_parser.parse(text_without_conversation)
        if not newly_completed_words:
            return
        
        # Update current state with newly completed words
        updated_words = current_words.copy()
        
        for new_word in newly_completed_words:
            # Find if this word ID already exists
            existing_index = None
            for i, existing_word in enumerate(updated_words):
                if existing_word.id == new_word.id:
                    existing_index = i
                    break
            
            if existing_index is not None:
                # Update existing word
                updated_words[existing_index] = new_word
            else:
                # Add new word, keeping words sorted by ID
                inserted = False
                for i, existing_word in enumerate(updated_words):
                    if new_word.id < existing_word.id:
                        updated_words.insert(i, new_word)
                        inserted = True
                        break
                if not inserted:
                    updated_words.append(new_word)
        
        # Generate diff and execute if using xdotool
        if USE_XDOTOOL:
            diff_result = diff_engine.compare(current_words, updated_words)
            output_manager.execute_diff(diff_result)
        else:
            # Fallback to old method - just output the text
            text_output = " ".join([word.text for word in updated_words])
            output_text_cross_platform(text_output)
        
        # Update current words
        current_words = updated_words
        
    except Exception as e:
        print(f"\nError in XML processing: {e}", file=sys.stderr)

def detect_and_execute_commands(text):
    """Detect commands in transcribed text and execute them. Returns the text with commands removed."""
    global CONVERSATION_HISTORY, LAST_TYPED_TEXT, current_words, word_parser
    
    # Command patterns to detect
    reset_patterns = [
        "reset conversation",
        "clear conversation", 
        "start over",
        "new conversation",
        "clear context"
    ]
    
    text_lower = text.lower().strip()
    
    # Check for reset commands
    for pattern in reset_patterns:
        if pattern in text_lower:
            print(f"\nCommand detected: '{pattern}' - Resetting conversation...")
            CONVERSATION_HISTORY.clear()
            LAST_TYPED_TEXT = ""
            # Clear XML processing state
            current_words.clear()
            if word_parser:
                word_parser.clear_buffer()
            # Remove the command from the text
            # Find the command in the original text (case-insensitive) and remove it
            import re
            text = re.sub(re.escape(pattern), '', text, flags=re.IGNORECASE).strip()
            break
    
    return text

# --- Configuration & Argument Parsing ---
# Load .env file specifically from the script's directory
script_dir = os.path.dirname(__file__)
dotenv_path = os.path.join(script_dir, '.env')
load_dotenv(dotenv_path=dotenv_path)

parser = argparse.ArgumentParser(
    description="Real-time dictation using Groq or Gemini.",
    formatter_class=argparse.ArgumentDefaultsHelpFormatter # Show defaults in help
)
parser.add_argument(
    "--provider",
    type=str,
    choices=['groq', 'gemini'],
    default=None, # Default to None, will be determined later if not provided
    help="The transcription provider to use ('groq' or 'gemini')."
)
parser.add_argument(
    "--model",
    type=str,
    default=None, # Default to None
    help="The specific model ID to use for the chosen provider."
)
parser.add_argument(
    "--trigger-key",
    type=str,
    default=DEFAULT_TRIGGER_KEY,
    help="The key name to trigger recording (e.g., 'alt_r', 'ctrl_r', 'f19')."
)
parser.add_argument(
    "--language",
    type=str,
    default=None,
    help="Optional: Language code (e.g., 'en', 'es') for transcription (Groq only)."
)
parser.add_argument(
    "--sample-rate",
    type=int,
    default=DEFAULT_SAMPLE_RATE,
    help="Audio sample rate in Hz."
)
parser.add_argument(
    "--channels",
    type=int,
    default=DEFAULT_CHANNELS,
    help="Number of audio channels (e.g., 1 for mono)."
)
parser.add_argument(
    "--use-xdotool",
    action="store_true",
    help="Use xdotool for typing text instead of clipboard paste. Linux only."
)

# Check if running interactively (no args other than script name, or only --use-xdotool)
args_without_script = sys.argv[1:]
interactive_mode = (len(args_without_script) == 0 or 
                   (len(args_without_script) == 1 and args_without_script[0] == '--use-xdotool'))

if interactive_mode:
    print("Running in interactive mode...")
    groq_key_present = bool(os.getenv("GROQ_API_KEY"))
    gemini_key_present = bool(os.getenv("GOOGLE_API_KEY"))

    if groq_key_present:
        print("Found GROQ_API_KEY in .env, selecting Groq as provider.")
        PROVIDER = 'groq'
    elif gemini_key_present:
        print("Found GOOGLE_API_KEY in .env (but no Groq key), selecting Gemini as provider.")
        PROVIDER = 'gemini'
    else:
        print("No API keys found in .env.")
        PROVIDER = select_from_list(['groq', 'gemini'], "Select a provider:")
        if not PROVIDER:
            print("No provider selected. Exiting.")
            sys.exit(0)

    # Select Model based on Provider
    if PROVIDER == 'groq':
        available_models = load_models_from_file("groq_models.txt")
        if not available_models:
             print("Could not load Groq models. Please ensure 'groq_models.txt' exists.", file=sys.stderr)
             sys.exit(1)
        MODEL_ID = select_from_list(available_models, f"Select a Groq model:")
    elif PROVIDER == 'gemini':
        available_models = load_models_from_file("gemini_models.txt")
        if not available_models:
             print("Could not load Gemini models. Please ensure 'gemini_models.txt' exists.", file=sys.stderr)
             sys.exit(1)
        MODEL_ID = select_from_list(available_models, f"Select a Gemini model:")

    if not MODEL_ID:
        print("No model selected. Exiting.")
        sys.exit(0)

    # Use default args for other settings in interactive mode
    # Parse the actual args to capture --use-xdotool if present
    args = parser.parse_args()
    LANGUAGE = args.language
    SAMPLE_RATE = args.sample_rate
    CHANNELS = args.channels
    TRIGGER_KEY_NAME = args.trigger_key
    USE_XDOTOOL = args.use_xdotool

else:
    # Parse arguments normally if provided
    args = parser.parse_args()
    PROVIDER = args.provider
    MODEL_ID = args.model
    LANGUAGE = args.language
    SAMPLE_RATE = args.sample_rate
    CHANNELS = args.channels
    TRIGGER_KEY_NAME = args.trigger_key
    USE_XDOTOOL = args.use_xdotool

    # Validate required args if not interactive
    if not PROVIDER or not MODEL_ID:
        parser.print_help()
        print("\nError: --provider and --model are required when running with arguments.", file=sys.stderr)
        sys.exit(1)


# --- Check platform for xdotool compatibility ---
if USE_XDOTOOL and platform.system() != "Linux":
    print(f"\nWarning: xdotool is only supported on Linux. Using clipboard method instead.", file=sys.stderr)
    USE_XDOTOOL = False

# --- Initialize XML processing components ---
def initialize_xml_processing():
    """Initialize XML word processing components."""
    global word_parser, diff_engine, output_manager
    
    word_parser = WordStreamParser()
    diff_engine = DiffEngine()
    
    if USE_XDOTOOL:
        try:
            output_manager = OutputManager()
            print("XML processing with xdotool output initialized.")
        except Exception as e:
            print(f"\nWarning: Failed to initialize xdotool output manager: {e}", file=sys.stderr)
            print("Falling back to clipboard method.", file=sys.stderr)
            output_manager = None
    else:
        output_manager = None
# --- Initialize Components ---
# Initialize XML processing components
initialize_xml_components()

# Initialize Provider Client and Trigger Key
if not initialize_provider_client():
    sys.exit(1) # Exit if client initialization failed

if not setup_trigger_key(TRIGGER_KEY_NAME):
    sys.exit(1) # Exit if trigger key setup failed


# --- Print Final Configuration ---
print(f"\n--- Configuration ---")
print(f"Provider:      {PROVIDER.upper()}")
print(f"Model:         {MODEL_ID}")
print(f"Trigger Key:   {TRIGGER_KEY_NAME}")
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
print(f"\nHold '{TRIGGER_KEY_NAME}' to record...")


# --- Audio Recording ---
def audio_callback(indata, frames, time, status):
    """This is called (from a separate thread) for each audio block."""
    if status:
        if status.input_overflow:
            # pass # Or print less verbose
             print("W", end='', flush=True) # Indicate overflow warning
        else:
            print(f"\nAudio callback status: {status}", file=sys.stderr)
    if is_recording:
        audio_queue.put(indata.copy())

def start_recording():
    """Starts the audio recording stream."""
    global is_recording, recording_stream
    if is_recording:
        return

    print("\nRecording started... ", end='', flush=True)
    is_recording = True
    audio_queue.queue.clear()

    try:
        recording_stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype=DTYPE,
            callback=audio_callback
        )
        recording_stream.start()
    except sd.PortAudioError as e:
        print(f"\nError starting audio stream: {e}", file=sys.stderr)
        print("Check audio device settings and permissions.", file=sys.stderr)
        is_recording = False
        recording_stream = None
    except Exception as e:
        print(f"\nUnexpected error during recording start: {e}", file=sys.stderr)
        is_recording = False
        recording_stream = None

def stop_recording_and_process():
    """Stops recording and processes the audio in a separate thread."""
    global is_recording, recording_stream
    if not is_recording:
        return

    print("Stopped. Processing... ", end='', flush=True)
    is_recording = False

    if recording_stream:
        try:
            recording_stream.stop()
            recording_stream.close()
        except sd.PortAudioError as e:
             print(f"\nError stopping/closing audio stream: {e}", file=sys.stderr)
        except Exception as e:
             print(f"\nUnexpected error stopping/closing audio stream: {e}", file=sys.stderr)
        finally:
            recording_stream = None

    audio_data = []
    while not audio_queue.empty():
        try:
            audio_data.append(audio_queue.get_nowait())
        except queue.Empty:
            break

    if not audio_data:
        print("No audio data recorded.")
        print(f"\nHold '{TRIGGER_KEY_NAME}' to record...") # Remind user
        return

    try:
        full_audio = np.concatenate(audio_data, axis=0)
    except ValueError as e:
        print(f"\nError concatenating audio data: {e}", file=sys.stderr)
        print(f"\nHold '{TRIGGER_KEY_NAME}' to record...") # Remind user
        return
    except Exception as e:
        print(f"\nUnexpected error combining audio: {e}", file=sys.stderr)
        print(f"\nHold '{TRIGGER_KEY_NAME}' to record...") # Remind user
        return

    processing_thread = threading.Thread(target=process_audio, args=(full_audio,))
    processing_thread.daemon = True
    processing_thread.start()

# --- Audio Processing & Transcription ---
def process_audio(audio_np):
    """Transcribes audio via the selected provider and outputs the result."""
    # print(f"Processing {audio_np.shape[0] / SAMPLE_RATE:.2f}s of audio...") # Less verbose
    text_to_output = None
    tmp_filename = None # For Groq

    # Need access to global clients/models initialized earlier
    global groq_client, gemini_model

    # Also need specific exception types if imported conditionally
    if PROVIDER == 'groq':
        from groq import GroqError
    elif PROVIDER == 'gemini':
        from google.api_core import exceptions as google_exceptions


    try:
        if PROVIDER == 'groq':
            if not groq_client:
                print("\nError: Groq client not initialized.", file=sys.stderr)
                return

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
                tmp_filename = tmp_file.name
                sf.write(tmp_filename, audio_np, SAMPLE_RATE)

            # print("Transcribing with Groq...")
            with open(tmp_filename, "rb") as file_for_groq:
                try:
                    # Create prompt with conversation context and XML formatting instructions
                    xml_instructions = (
                        "Format words as <ID>word</ID> where ID starts at 10 and increments by 10. "
                        "Example: <10>hello</10><20>world</20><30>today</30>. "
                        "Only reuse ID numbers when editing previous words. "
                        "After edits, resume with next available ID. "
                        "Never output partial XML tags. "
                        "Wrap any non-transcription responses in <conversation>...</conversation>. "
                        "Keep conversations separate from transcription output. "
                        "Never mix conversation and transcription tags."
                    )
                    
                    prompt = xml_instructions
                    if CONVERSATION_HISTORY:
                        context = " ".join(CONVERSATION_HISTORY[-3:])  # Last 3 exchanges
                        prompt += f" Previous context: {context}. Continue the conversation:"
                    
                    transcription_params = {
                        "file": (os.path.basename(tmp_filename), file_for_groq.read()),
                        "model": MODEL_ID,
                        "language": LANGUAGE
                    }
                    
                    # Add prompt (always include XML instructions)
                    transcription_params["prompt"] = prompt
                    
                    transcription = groq_client.audio.transcriptions.create(**transcription_params)
                    text_to_output = transcription.text
                    print(f"Transcription: {text_to_output}")
                except GroqError as e:
                    print(f"\nGroq API Error: {e}", file=sys.stderr)
                except Exception as e:
                    print(f"\nUnexpected error during Groq transcription: {e}", file=sys.stderr)

        elif PROVIDER == 'gemini':
            if not gemini_model:
                print("\nError: Gemini model not initialized.", file=sys.stderr)
                return

            wav_bytes_io = io.BytesIO()
            sf.write(wav_bytes_io, audio_np, SAMPLE_RATE, format='WAV', subtype='PCM_16')
            wav_bytes = wav_bytes_io.getvalue()
            wav_bytes_io.close()

            if len(wav_bytes) > 18 * 1024 * 1024:
                 print("\nWarning: Audio data >18MB, may fail inline Gemini request.")

            # print("Transcribing with Gemini...")
            try:
                xml_instructions = (
                    "Format words as <ID>word</ID> where ID starts at 10 and increments by 10. "
                    "Example: <10>hello</10><20>world</20><30>today</30>. "
                    "Only reuse ID numbers when editing previous words. "
                    "After edits, resume with next available ID. "
                    "Never output partial XML tags. "
                    "Wrap any non-transcription responses in <conversation>...</conversation>. "
                    "Keep conversations separate from transcription output. "
                    "Never mix conversation and transcription tags."
                )
                
                prompt = f"Transcript with XML formatting: {xml_instructions}"
                if CONVERSATION_HISTORY:
                    context = " ".join(CONVERSATION_HISTORY[-3:])
                    prompt += f" Previous context: {context}. Continue the conversation:"
                
                audio_blob = {"mime_type": "audio/wav", "data": wav_bytes}
                contents = [prompt, audio_blob]
                response = gemini_model.generate_content(contents=contents)

                # Check response structure carefully
                text_to_output = None
                if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
                     text_to_output = "".join(part.text for part in response.candidates[0].content.parts if hasattr(part, 'text'))
                elif hasattr(response, 'text'): # Fallback for simpler structures if any
                     text_to_output = response.text

                if text_to_output:
                    print(f"Transcription: {text_to_output}")
                else:
                    print("\nGemini did not return text.")
                    # print(f"Full Response: {response}") # Debugging

            except google_exceptions.InvalidArgument as e:
                 print(f"\nGemini API Error (Invalid Argument): {e}", file=sys.stderr)
            except google_exceptions.PermissionDenied as e:
                 print(f"\nGemini API Error (Permission Denied): {e}", file=sys.stderr)
            except google_exceptions.ResourceExhausted as e:
                 print(f"\nGemini API Error (Rate Limit/Quota): {e}", file=sys.stderr)
            except Exception as e:
                print(f"\nUnexpected error during Gemini transcription: {e}", file=sys.stderr)

        if text_to_output:
            # Process XML words and handle continuous editing
            process_xml_transcription(text_to_output)
        else:
            print("No transcription result.")


    except sf.SoundFileError as e:
        print(f"\nError processing sound file data: {e}", file=sys.stderr)
    except Exception as e:
        print(f"\nError in process_audio: {e}", file=sys.stderr)
    finally:
        if tmp_filename and os.path.exists(tmp_filename):
            try:
                os.remove(tmp_filename)
            except OSError as e:
                print(f"\nError deleting temp file {tmp_filename}: {e}", file=sys.stderr)
        # Remind user how to record again after processing finishes
        print(f"\nHold '{TRIGGER_KEY_NAME}' to record...")


def process_xml_transcription(text):
    """Process XML transcription text using the word processing pipeline."""
    global current_words, word_parser, diff_engine, output_manager, CONVERSATION_HISTORY
    
    try:
        # Check for conversation tags first
        import re
        conversation_pattern = re.compile(r'<conversation>(.*?)</conversation>', re.DOTALL)
        conversation_matches = conversation_pattern.findall(text)
        
        # Process conversation content
        for conversation_content in conversation_matches:
            content = conversation_content.strip()
            if content:
                # Process commands in conversation content
                cleaned_content = detect_and_execute_commands(content)
                if cleaned_content.strip():
                    print(f"AI: {cleaned_content}")
                    CONVERSATION_HISTORY.append(cleaned_content)
                    # Keep only last 10 exchanges
                    if len(CONVERSATION_HISTORY) > 10:
                        CONVERSATION_HISTORY.pop(0)
        
        # Remove conversation tags from text before processing words
        text_without_conversation = conversation_pattern.sub('', text)
        
        # Parse XML to extract words
        newly_completed_words = word_parser.parse(text_without_conversation)
        if not newly_completed_words:
            return
        
        # Update current state with newly completed words
        updated_words = current_words.copy()
        
        for new_word in newly_completed_words:
            # Find if this word ID already exists
            existing_index = None
            for i, existing_word in enumerate(updated_words):
                if existing_word.id == new_word.id:
                    existing_index = i
                    break
            
            if existing_index is not None:
                # Update existing word
                updated_words[existing_index] = new_word
            else:
                # Add new word, keeping words sorted by ID
                inserted = False
                for i, existing_word in enumerate(updated_words):
                    if new_word.id < existing_word.id:
                        updated_words.insert(i, new_word)
                        inserted = True
                        break
                if not inserted:
                    updated_words.append(new_word)
        
        # Calculate diff and execute changes
        diff_result = diff_engine.compare(current_words, updated_words)
        
        if output_manager and USE_XDOTOOL:
            # Use the sophisticated output manager for xdotool
            try:
                output_manager.execute_diff(diff_result)
            except XdotoolError as e:
                print(f"\nxdotool error: {e}", file=sys.stderr)
                print("Falling back to clipboard method...", file=sys.stderr)
                # Fall back to clipboard method
                if diff_result.new_text:
                    full_text = ' '.join(w.text for w in updated_words)
                    output_text_cross_platform(full_text)
        else:
            # Use clipboard method - but we still need to handle the diff properly
            if diff_result.backspaces > 0 or diff_result.new_text:
                # For clipboard method, output the full corrected text
                full_text = ' '.join(w.text for w in updated_words)
                output_text_cross_platform(full_text)
        
        # Update current words state
        current_words = updated_words
        
        # Add to conversation history
        if updated_words:
            full_text = ' '.join(w.text for w in updated_words)
            # Process commands in the full text
            cleaned_text = detect_and_execute_commands(full_text)
            if cleaned_text.strip() and cleaned_text != full_text:
                # A command was detected and executed, update conversation history
                CONVERSATION_HISTORY.append(cleaned_text)
                if len(CONVERSATION_HISTORY) > 10:
                    CONVERSATION_HISTORY.pop(0)
    
    except Exception as e:
        print(f"\nError processing XML transcription: {e}", file=sys.stderr)

def type_with_xdotool(new_text):
    """Uses xdotool to type text directly with editing support via backspace."""
    global LAST_TYPED_TEXT
    
    try:
        # Find the common prefix between previous and new text
        common_prefix_length = 0
        for i in range(min(len(LAST_TYPED_TEXT), len(new_text))):
            if LAST_TYPED_TEXT[i] == new_text[i]:
                common_prefix_length += 1
            else:
                break
        
        # Calculate backspaces needed
        backspaces_needed = len(LAST_TYPED_TEXT) - common_prefix_length
        
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
        LAST_TYPED_TEXT = new_text
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

def output_text_cross_platform(text):
    """Outputs text using either xdotool or clipboard paste based on settings."""
    global USE_XDOTOOL
    
    # Use xdotool if selected and on Linux
    current_os = platform.system()
    if USE_XDOTOOL and current_os == "Linux":
        # Try xdotool first
        if type_with_xdotool(text):
            return
        # Fall back to clipboard if xdotool fails
        print("Falling back to clipboard method...", file=sys.stderr)
    
    # Default clipboard method
    try:
        pyperclip.copy(text)
        # print("Copied to clipboard.") # Less verbose

        paste_key_char = 'v' # Common paste character
        if current_os == "Darwin": # macOS
            modifier_key = keyboard.Key.cmd
        elif current_os == "Windows" or current_os == "Linux":
            modifier_key = keyboard.Key.ctrl
        else:
            print(f"\nWarning: Unsupported OS '{current_os}' for auto-pasting. Text copied.", file=sys.stderr)
            return

        # print(f"Simulating paste ({modifier_key} + {paste_key_char})...")
        with keyboard_controller.pressed(modifier_key):
             keyboard_controller.press(paste_key_char)
             keyboard_controller.release(paste_key_char)
        # print("Paste simulated.")

    except pyperclip.PyperclipException as e:
        print(f"\nError copying to clipboard: {e}", file=sys.stderr)
        print("Ensure clipboard utilities are installed (e.g., xclip on Linux).")
    except Exception as e:
        print(f"\nUnexpected error during text output: {e}", file=sys.stderr)


# --- Key Listener Callbacks ---
def on_press(key):
    global is_recording
    try:
        if key == TRIGGER_KEY and not is_recording:
            start_recording()
    except Exception as e:
        print(f"\nError in on_press: {e}", file=sys.stderr)


def on_release(key):
    global is_recording
    try:
        if key == TRIGGER_KEY and is_recording:
            stop_recording_and_process()

        if key == keyboard.Key.esc:
            print("\nExiting...")
            if recording_stream:
                try:
                    if recording_stream.active: recording_stream.stop()
                    recording_stream.close()
                except Exception as e: pass # Ignore errors on exit
            return False # Stop listener
    except Exception as e:
        print(f"\nError in on_release: {e}", file=sys.stderr)


# --- Main Execution ---
if __name__ == "__main__":
    listener = None
    try:
        try:
            # print("\nAvailable Input Audio Devices:") # Less verbose startup
            # print(sd.query_devices())
            # Check if default device works, maybe?
            with sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, dtype=DTYPE, callback=lambda i,f,t,s: None):
                pass
            print("Audio device check successful.")
        except sd.PortAudioError as e:
             print(f"\nFATAL: Audio device error: {e}", file=sys.stderr)
             print("Please check connection, selection, and permissions.", file=sys.stderr)
             sys.exit(1)
        except Exception as e:
            print(f"\nWarning: Could not query/test audio devices: {e}", file=sys.stderr)


        listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        listener.start()
        # print("\nListener started. Waiting for trigger key...") # Moved earlier
        listener.join()

    except ImportError as e:
        print(f"\nImport Error: {e}", file=sys.stderr)
        print("Please ensure all required libraries are installed (see README).", file=sys.stderr)
    except KeyboardInterrupt:
        print("\nCtrl+C detected. Exiting.")
    except Exception as e:
        print(f"\nAn unexpected error occurred in main execution: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc() # Print full traceback for unexpected errors
    finally:
        print("\nCleaning up...")
        if listener and listener.is_alive():
            listener.stop()
        if recording_stream:
            try:
                if recording_stream.active: recording_stream.stop()
                recording_stream.close()
                print("Audio stream stopped.")
            except Exception as e: pass # Ignore errors on final cleanup
        print("Exited.")