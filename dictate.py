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
import time
import platform  # To detect OS for key combinations
import shlex  # For safe shell argument escaping
import re  # For regex processing
import signal
from pynput import keyboard

# Configuration management
from config_manager import ConfigManager

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
from lib.conversation_state import ConversationManager, ConversationState

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

# Conversation management
conversation_manager = None

# Streaming state
streaming_buffer = ""
last_processed_position = 0

# Provider-specific instruction additions (currently blank, can be customized per provider)
GROQ_SPECIFIC_INSTRUCTIONS = ""
GEMINI_SPECIFIC_INSTRUCTIONS = ""

# --- Helper Functions ---


def initialize_xml_components():
    """Initialize the XML processing components."""
    global word_parser, diff_engine, output_manager, conversation_manager
    word_parser = WordStreamParser()
    diff_engine = DiffEngine()
    output_manager = OutputManager()
    conversation_manager = ConversationManager()
    conversation_manager.load_conversation()

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
    if key_name is None or str(key_name).lower() in ("", "none", "disabled", "off"):
        TRIGGER_KEY = None
        return True
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

def get_xml_instructions(provider_specific=""):
    """
    Get the common XML instructions with optional provider-specific additions.
    
    Args:
        provider_specific: Additional instructions specific to the provider
        
    Returns:
        Complete instruction string
    """
    common_instructions = (
        "You are an intelligent transcription assistant. Use COMMON SENSE to determine if the user is dictating content or giving you editing instructions.\n\n"
        "RESPONSE FORMAT - Always respond using this EXACT format:\n"
        "<x>\n"
        "<tx>literal translation goes here</tx>\n"
        "<int>model interpretation goes here</int>\n"
        "<conv>conversational discussion goes here only if conversation is necessary</conv>\n"
        "<update><10>processed content </10><20>goes here </20><30>with proper formatting.</30></update>\n"
        "</x>\n\n"
        "ENHANCED BEHAVIOR:\n"
        "- Always use proper grammar and correct any grammatical errors you detect\n"
        "- If user gives multiple correction statements, pay attention to following their directions\n"
        "- Read between the lines - capture meaning and user's voice rather than exact words\n"
        "- Handle stutters, false starts, and unclear speech by interpreting intent\n"
        "- Prioritize natural, well-formed output over literal transcription\n"
        "- Always provide helpful feedback when appropriate\n\n"
        "SECTION DETAILS:\n"
        "- <tx>: Literal word-for-word transcription of what you heard\n"
        "- <int>: Your interpretation of what the user actually wants. This is CRITICAL - analyze whether they are:\n"
        "  * DICTATING content to be written (then interpret their intended meaning, fix grammar, clarify unclear speech)\n"
        "  * GIVING INSTRUCTIONS for editing (then describe what editing action they want performed)\n"
        "  * DO NOT simply duplicate the translation - provide meaningful interpretation of user intent\n"
        "- <conv>: Include ONLY when conversation/clarification is needed\n"
        "- <update>: Final processed content formatted as <ID>content</ID>\n\n"
        "SPACING CONTROL:\n"
        "- YOU have full control over all spacing, punctuation, and whitespace\n"
        "- Each <ID>content</ID> tag contains exactly what you want at that position\n"
        "- SPACES BETWEEN TAGS ARE OMITTED - only content inside tags is used\n"
        "- Include spaces, punctuation, and formatting within your tags as needed\n"
        "- Example: <10>Hello world, </10><20>this works perfectly!</20> renders as 'Hello world, this works perfectly!'\n"
        "- Bad: <10>Hello</10> <20>world</20> renders as 'Helloworld' (space between tags ignored)\n"
        "- Good: <10>Hello world </10><20>today!</20> renders as 'Hello world today!' (space inside first tag)\n"
        "- PRESERVE SPACING: Always include a leading space in a tag that follows punctuation. Example: <20>trees.</20><30> One day</30>\n\n"
        "DICTATION vs INSTRUCTION DETECTION:\n"
        "- DICTATION: User speaking content to be written (flows naturally, continues previous text)\n"
        "- INSTRUCTION: User giving you commands (phrases like 'fix this', 'change that', 'make it better', 'turn this into', 'correct the grammar')\n"
        "- Use context clues: if it sounds like they're telling YOU to do something, it's an instruction\n"
        "- Instructions often start mid-sentence or break the flow of normal speech\n\n"
        "DICTATION MODE:\n"
        "- Transcribe speech using PHRASE-LEVEL granularity in <update> section\n"
        "- Group words into logical chunks (3-8 words per tag is ideal)\n"
        "- Continue from highest existing ID + 10 (if last ID was 40, start at 50)\n"
        "- Example: <50>Testing the system </50><60>with multiple phrases </60><70>for better efficiency.</70>\n"
        "- Avoid excessive tags like: <10>Testing </10><20>1, </20><30>2, </30><40>3.</40>\n\n"
        "INSTRUCTION MODE:\n"
        "- Don't transcribe the instruction itself in <update>\n"
        "- Analyze the existing conversation text to understand what they want changed\n"
        "- Make the requested changes using existing IDs: <30>newword </30> or <20></20> for deletion\n"
        "- Common instructions: 'fix grammar', 'make it formal', 'turn this into a paragraph', 'correct spelling'\n\n"
        "EXAMPLES:\n"
        "- 'Hello world fix the grammar' → Likely: 'Hello world' (dictation) + 'fix the grammar' (instruction)\n"
        "- 'Turn this sentence into a nice paragraph' → Pure instruction, edit existing text\n"
        "- 'Today is sunny and warm' → Pure dictation, transcribe normally\n\n"
        "UPDATE SECTION RULES:\n"
        "- Use empty tags like <50></50> to delete word ID 50\n"
        "- YOU control all spacing, punctuation, and whitespace within tags\n"
        "- SPACES BETWEEN TAGS ARE IGNORED - only content inside tags is used\n"
        "- All whitespace including carriage returns must be inside tags - anything between tags is completely ignored. Newlines are preserved.\n"
        "- Escape XML characters: use &amp; for &, &gt; for >, &lt; for < inside content\n"
        "- Group words into logical phrases (3-8 words per tag ideal)\n"
        "- Continue from highest existing ID + 10\n"
        "- Example: <50>Testing the system </50><60>with multiple phrases.</60>\n"
        "\n"
        "NON-DUPLICATION GUARANTEE:\n"
        "- <int> must not be a verbatim copy of <tx> after trimming and trivial punctuation normalization, unless the utterance is pure dictation and equals the intended cleaned output.\n"
        "- For dictation with fillers (e.g., 'um', 'uh', repetitions), <int> contains the minimal intended words only.\n"
        "- For instructions (e.g., 'fix grammar', 'replace X with Y', 'delete lines 20 to 40'), <int> is an imperative edit request targeting the current conversation state.\n"
        "EXAMPLES:\n"
        "- Input: 'um okay product roadmap' → <tx>: 'um okay product roadmap'; <int>: 'product roadmap'\n"
        "- Input: 'replace foo with bar and remove the second paragraph' → <tx>: 'replace foo with bar and remove the second paragraph'; <int>: 'Replace `foo` with `bar` and remove the second paragraph.'"
        "\n"
        "\n"
        "RESETTING STATE:\n"
        "- If the previous content should be cleared, you must emit a reset tag before any updates.\n"
        "- Emit <reset/> as the FIRST tag in your response (immediately before <update> inside <x>).\n"
        "- Do not emit deletions of old IDs when resetting; after <reset/>, start fresh IDs at 10, 20, 30 ... and reference only new IDs.\n"
        "- When to issue <reset/>:\n"
        "  * User explicitly says: 'reset conversation', 'clear conversation/context', 'start over', 'new conversation'.\n"
        "  * Topic shifts significantly such that prior text is no longer relevant.\n"
        "\n"
        "RESETTED RESPONSE EXAMPLE:\n"
        "<x>\n"
        "<reset/>\n"
        "<tx> ... </tx>\n"
        "<int> ... </int>\n"
        "<conv> ... </conv>\n"
        "<update><10>Fresh start </10><20>with new IDs.</20></update>\n"
        "</x>"
    )
    
    if provider_specific.strip():
        return common_instructions + "\n\n" + provider_specific
    return common_instructions


def detect_and_execute_commands(text):
    """Detect commands in transcribed text and execute them. Returns the text with commands removed."""
    global CONVERSATION_HISTORY, LAST_TYPED_TEXT, current_words, word_parser, conversation_manager
    
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
            reset_all_state()
            import re
            text = re.sub(re.escape(pattern), '', text, flags=re.IGNORECASE).strip()
            break
    
    return text

# --- Configuration & Argument Parsing ---
# Initialize configuration manager
config_manager = ConfigManager()
if not config_manager.parse_configuration():
    sys.exit(1)

# Get configuration values
config = config_manager.get_config()
PROVIDER = config['provider']
MODEL_ID = config['model_id']
LANGUAGE = config['language']
SAMPLE_RATE = config['sample_rate']
CHANNELS = config['channels']
TRIGGER_KEY_NAME = config['trigger_key_name']
USE_XDOTOOL = config['use_xdotool']


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
print(f"Trigger Key:   {'disabled' if TRIGGER_KEY is None else TRIGGER_KEY_NAME}")
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

# Display system instructions once at startup
print("\n" + "="*60)
print("SYSTEM INSTRUCTIONS FOR MODEL:")
print("-" * 60)
# Show provider-specific instructions for current provider
provider_specific = GROQ_SPECIFIC_INSTRUCTIONS if PROVIDER == 'groq' else GEMINI_SPECIFIC_INSTRUCTIONS
xml_instructions = get_xml_instructions(provider_specific)
print(xml_instructions)
print("="*60)

if TRIGGER_KEY is not None:
    print(f"\nHold '{TRIGGER_KEY_NAME}' to record...")
else:
    print("\nKeyboard trigger disabled. Use SIGUSR1 to start and SIGUSR2 to stop.")


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
        if TRIGGER_KEY is not None:
            print(f"\nHold '{TRIGGER_KEY_NAME}' to record...")
        else:
            print("\nKeyboard trigger disabled. Use SIGUSR1 to start and SIGUSR2 to stop.")
        return

    try:
        full_audio = np.concatenate(audio_data, axis=0)
    except ValueError as e:
        print(f"\nError concatenating audio data: {e}", file=sys.stderr)
        if TRIGGER_KEY is not None:
            print(f"\nHold '{TRIGGER_KEY_NAME}' to record...")
        else:
            print("\nKeyboard trigger disabled. Use SIGUSR1 to start and SIGUSR2 to stop.")
        return
    except Exception as e:
        print(f"\nUnexpected error combining audio: {e}", file=sys.stderr)
        if TRIGGER_KEY is not None:
            print(f"\nHold '{TRIGGER_KEY_NAME}' to record...")
        else:
            print("\nKeyboard trigger disabled. Use SIGUSR1 to start and SIGUSR2 to stop.")
        return

    processing_thread = threading.Thread(target=process_audio, args=(full_audio,))
    processing_thread.daemon = True
    processing_thread.start()

# --- Audio Processing & Transcription ---
def process_audio(audio_np):
    """Transcribes audio via the selected provider and outputs the result with real-time streaming."""
    # print(f"Processing {audio_np.shape[0] / SAMPLE_RATE:.2f}s of audio...") # Less verbose
    tmp_filename = None # For Groq

    # Need access to global clients/models initialized earlier
    global groq_client, gemini_model

    # Also need specific exception types if imported conditionally
    if PROVIDER == 'groq':
        from groq import GroqError
    elif PROVIDER == 'gemini':
        from google.api_core import exceptions as google_exceptions


    try:
        reset_streaming_state()
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
                    xml_instructions = get_xml_instructions(GROQ_SPECIFIC_INSTRUCTIONS)
                    
                    # Display conversation flow
                    print("\n" + "="*60)
                    print("SENDING TO MODEL:")
                    print("[conversation context being sent]")
                    
                    conversation_xml = ""
                    if conversation_manager and conversation_manager.state.words:
                        conversation_xml = conversation_manager.state.to_xml()
                        print(f"XML markup: {conversation_xml}")
                        
                        # Show compiled view
                        compiled_text = conversation_manager.state.to_text()
                        print(f"Rendered text: {compiled_text}")
                    else:
                        print("XML markup: [no conversation history]")
                        print("Rendered text: [empty]")
                    
                    print(f"Audio file: {os.path.basename(tmp_filename)}")
                    print("-" * 60)
                    
                    prompt = xml_instructions
                    if conversation_xml:
                        # Show both XML markup and rendered text to the model
                        compiled_text = conversation_manager.state.to_text()
                        prompt += f" Current conversation XML: {conversation_xml}\nCurrent conversation text: {compiled_text}"
                    
                    transcription_params = {
                        "file": (os.path.basename(tmp_filename), file_for_groq.read()),
                        "model": MODEL_ID,
                        "language": LANGUAGE
                    }
                    
                    # Add prompt (always include XML instructions)
                    transcription_params["prompt"] = prompt
                    
                    # Use streaming for Groq if available
                    try:
                        # Check if streaming is available for transcription
                        transcription = groq_client.audio.transcriptions.create(**transcription_params)
                        text_to_output = transcription.text
                        
                        # Apply final state without non-stream display
                        process_xml_transcription(text_to_output)
                        
                    except Exception as stream_error:
                        print(f"Streaming not available, using standard response: {stream_error}")
                        transcription = groq_client.audio.transcriptions.create(**transcription_params)
                        text_to_output = transcription.text
                        process_xml_transcription(text_to_output)
                        
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
                xml_instructions = get_xml_instructions(GEMINI_SPECIFIC_INSTRUCTIONS)
                
                # Display conversation flow
                print("\n" + "="*60)
                print("SENDING TO MODEL:")
                print("[conversation context being sent]")
                
                conversation_xml = ""
                if conversation_manager and conversation_manager.state.words:
                    conversation_xml = conversation_manager.state.to_xml()
                    print(f"XML markup: {conversation_xml}")
                    
                    # Show compiled view
                    compiled_text = conversation_manager.state.to_text()
                    print(f"Rendered text: {compiled_text}")
                else:
                    print("XML markup: [no conversation history]")
                    print("Rendered text: [empty]")
                
                print(f"Audio file: [audio_data.wav]")
                print("-" * 60)
                
                prompt = f"Transcript with XML formatting: {xml_instructions}"
                if conversation_xml:
                    # Show both XML markup and rendered text to the model
                    compiled_text = conversation_manager.state.to_text()
                    prompt += f" Current conversation XML: {conversation_xml}\nCurrent conversation text: {compiled_text}"
                
                audio_blob = {"mime_type": "audio/wav", "data": wav_bytes}
                contents = [prompt, audio_blob]
                
                # Use streaming for Gemini
                try:
                    response = gemini_model.generate_content(
                        contents=contents,
                        stream=True
                    )

                    reset_streaming_state()
                    print("\nRECEIVED FROM MODEL (streaming):")
                    accumulated_text = ""
                    for chunk in response:
                        if chunk.candidates and chunk.candidates[0].content and chunk.candidates[0].content.parts:
                            chunk_text = "".join(part.text for part in chunk.candidates[0].content.parts if hasattr(part, 'text'))
                            if chunk_text:
                                print(chunk_text, end='', flush=True)
                                accumulated_text += chunk_text
                                process_streaming_chunk(chunk_text)
                    print()  # New line after streaming

                    if accumulated_text:
                        process_xml_transcription(accumulated_text)
                    else:
                        print("\nGemini did not return text.")

                except Exception as stream_error:
                    print(f"Streaming failed, using standard response: {stream_error}")
                    response = gemini_model.generate_content(contents=contents)

                    # Check for safety ratings first
                    if response.candidates and response.candidates[0].safety_ratings:
                        print("\nSafety Ratings:")
                        for rating in response.candidates[0].safety_ratings:
                            print(f"  {rating.category.name}: {rating.probability.name}")

                    # Check response structure carefully
                    text_to_output = None
                    if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
                         text_to_output = "".join(part.text for part in response.candidates[0].content.parts if hasattr(part, 'text'))
                    elif hasattr(response, 'text'): # Fallback for simpler structures if any
                         text_to_output = response.text

                    if text_to_output:
                        process_xml_transcription(text_to_output)
                    else:
                        print("\nGemini did not return text.")
                        if response.candidates and response.candidates[0].finish_reason:
                            print(f"Finish reason: {response.candidates[0].finish_reason.name}")

            except google_exceptions.InvalidArgument as e:
                 print(f"\nGemini API Error (Invalid Argument): {e}", file=sys.stderr)
            except google_exceptions.PermissionDenied as e:
                 print(f"\nGemini API Error (Permission Denied): {e}", file=sys.stderr)
            except google_exceptions.ResourceExhausted as e:
                 print(f"\nGemini API Error (Rate Limit/Quota): {e}", file=sys.stderr)
            except Exception as e:
                print(f"\nUnexpected error during Gemini transcription: {e}", file=sys.stderr)

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
        if TRIGGER_KEY is not None:
            print(f"\nHold '{TRIGGER_KEY_NAME}' to record...")
        else:
            print("\nKeyboard trigger disabled. Use SIGUSR1 to start and SIGUSR2 to stop.")


def process_streaming_response(text_to_output):
    """No-op: non-stream final display removed."""
    if not text_to_output:
        return
    # Keep state consistent without extra console output
    process_xml_transcription(text_to_output)


def process_streaming_chunk(chunk_text):
    """Process streaming text chunks and apply real-time updates."""
    global streaming_buffer, last_processed_position, current_words, word_parser, diff_engine, output_manager, conversation_manager
    
    # Add chunk to buffer
    streaming_buffer += chunk_text
    
    import re

    # Detect and handle <reset> tags in the stream
    reset_pattern = re.compile(r'<reset\s*/>|<reset>.*?</reset>', re.DOTALL | re.IGNORECASE)
    if reset_pattern.search(streaming_buffer):
        last_match = None
        for m in reset_pattern.finditer(streaming_buffer):
            last_match = m
        reset_all_state()
        if last_match:
            streaming_buffer = streaming_buffer[last_match.end():]
    
    # Try to extract complete XML tags from buffer
    
    # Look for complete <update> sections with word tags
    update_pattern = re.compile(r'<update>(.*?)</update>', re.DOTALL)
    update_matches = update_pattern.findall(streaming_buffer)
    
    if update_matches:
        # Process the most recent complete update section
        latest_update = update_matches[-1]
        
        # Extract word tags from the update
        word_pattern = re.compile(r'<(\d+)>(.*?)</\1>', re.DOTALL)
        word_matches = word_pattern.findall(latest_update)
        
        if word_matches:
            # Create word objects from matches
            new_words = []
            for word_id_str, word_text in word_matches:
                word_id = int(word_id_str)
                # Handle empty tags as deletions
                if word_text.strip() == "":
                    new_words.append(DictationWord(id=word_id, text=None))
                else:
                    new_words.append(DictationWord(id=word_id, text=word_text))
            
            # Update conversation state incrementally
            if conversation_manager:
                for word in new_words:
                    if word.text is None:
                        conversation_manager.state.delete_word(word.id)
                    else:
                        conversation_manager.state.update_word(word.id, word.text)
                
                # Build updated words list
                word_items = list(conversation_manager.state.words.items())
                word_items.sort(key=lambda x: x[0])
                updated_words = [DictationWord(id=word_id, text=text) for word_id, text in word_items]
                
                # Calculate and apply diff for real-time updates
                diff_result = diff_engine.compare(current_words, updated_words)
                
                if output_manager and USE_XDOTOOL:
                    try:
                        output_manager.execute_diff(diff_result)
                    except XdotoolError as e:
                        print(f"\nxdotool error: {e}", file=sys.stderr)
                        # Fall back to clipboard for this chunk
                        if diff_result.new_text:
                            full_text = conversation_manager.state.to_text_from_words(updated_words)
                            output_text_cross_platform(full_text)
                else:
                    # Use clipboard method for real-time updates
                    if diff_result.backspaces > 0 or diff_result.new_text:
                        full_text = conversation_manager.state.to_text_from_words(updated_words)
                        output_text_cross_platform(full_text)
                
                # Update current words state
                current_words = updated_words
                
                # Show real-time progress
                compiled_text = conversation_manager.state.to_text()
                print(f"\r[Streaming] {compiled_text}", end='', flush=True)


def reset_streaming_state():
    """Reset streaming state for new transcription."""
    global streaming_buffer, last_processed_position
    streaming_buffer = ""
    last_processed_position = 0


def reset_all_state():
    """Reset all stored state for a fresh conversation/update baseline."""
    global CONVERSATION_HISTORY, LAST_TYPED_TEXT, current_words, word_parser, conversation_manager
    # Clear conversation/history surfaces
    CONVERSATION_HISTORY.clear()
    LAST_TYPED_TEXT = ""
    # Clear XML processing state
    current_words.clear()
    if word_parser:
        word_parser.clear_buffer()
    # Reset conversation state
    if conversation_manager:
        conversation_manager.reset_conversation()
    # Reset streaming accumulators
    reset_streaming_state()


def process_xml_transcription(text):
    """Process XML transcription text using the word processing pipeline."""
    global current_words, word_parser, diff_engine, output_manager, conversation_manager
    
    try:
        # Check for conversation tags first
        import re
        conversation_pattern = re.compile(r'<conversation>(.*?)</conversation>', re.DOTALL)
        conversation_matches = conversation_pattern.findall(text)

        # Detect and handle <reset> tags before processing words
        reset_pattern = re.compile(r'<reset\s*/>|<reset>.*?</reset>', re.DOTALL | re.IGNORECASE)
        if reset_pattern.search(text):
            reset_all_state()
            text = reset_pattern.sub('', text)
        
        # Process conversation content
        for conversation_content in conversation_matches:
            content = conversation_content.strip()
            if content:
                # Process commands in conversation content
                cleaned_content = detect_and_execute_commands(content)
                if cleaned_content.strip():
                    print(f"AI: {cleaned_content}")
        
        # Remove conversation tags from text before processing words
        text_without_conversation = conversation_pattern.sub('', text)
        
        # Parse XML to extract words (including deletions)
        newly_parsed_words = word_parser.parse(text_without_conversation)
        if not newly_parsed_words:
            return
        
        # Update conversation state with all parsed words
        if conversation_manager:
            for word in newly_parsed_words:
                if word.text is None:
                    # Handle deletion
                    conversation_manager.state.delete_word(word.id)
                else:
                    # Handle update/addition
                    conversation_manager.state.update_word(word.id, word.text)
            
            # Conversation state updated in memory
            
            # Build current words list from conversation state for diff processing
            word_items = list(conversation_manager.state.words.items())
            word_items.sort(key=lambda x: x[0])  # Sort by ID
            updated_words = [DictationWord(id=word_id, text=text) for word_id, text in word_items]
        else:
            # Fallback to old behavior if conversation manager not available
            updated_words = current_words.copy()
            
            for new_word in newly_parsed_words:
                if new_word.text is None:
                    # Handle deletion - remove from updated_words
                    updated_words = [w for w in updated_words if w.id != new_word.id]
                else:
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
                    full_text = conversation_manager.state.to_text_from_words(updated_words)
                    output_text_cross_platform(full_text)
        else:
            # Use clipboard method - but we still need to handle the diff properly
            if diff_result.backspaces > 0 or diff_result.new_text:
                # For clipboard method, output the full corrected text
                full_text = conversation_manager.state.to_text_from_words(updated_words)
                output_text_cross_platform(full_text)
        
        # Update current words state
        current_words = updated_words
    
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


# --- POSIX Signal Handlers ---
def handle_sigusr1(signum, frame):
    global is_recording
    try:
        if not is_recording:
            start_recording()
    except Exception as e:
        print(f"\nError in SIGUSR1 handler: {e}", file=sys.stderr)


def handle_sigusr2(signum, frame):
    global is_recording
    try:
        if is_recording:
            stop_recording_and_process()
    except Exception as e:
        print(f"\nError in SIGUSR2 handler: {e}", file=sys.stderr)


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
            return
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


        try:
            signal.signal(signal.SIGUSR1, handle_sigusr1)
            signal.signal(signal.SIGUSR2, handle_sigusr2)
        except Exception as _e:
            pass

        if TRIGGER_KEY is not None:
            listener = keyboard.Listener(on_press=on_press, on_release=on_release)
            listener.start()
            # print("\nListener started. Waiting for trigger key...") # Moved earlier
            listener.join()
        else:
            while True:
                time.sleep(1)

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