import os
import sys
import argparse
from dotenv import load_dotenv
from lib.pr_log import pr_err, pr_notice


class ConfigManager:
    """Manages configuration, argument parsing, and interactive model selection for dictation."""
    
    def __init__(self):
        self.provider = None
        self.model_id = None
        self.language = None
        self.sample_rate = 16000
        self.channels = 1
        self.trigger_key_name = 'alt_r'
        self.debug_enabled = False
        self.litellm_debug = False
        self.xml_stream_debug = False
        self.no_trigger_key = False
        self.xdotool_rate = None
        self.reset_state_each_response = False

        # API key configuration
        self.api_key = None

        # Audio source configuration
        self.audio_source = "raw"

        # Transcription model configuration
        self.transcription_model = "huggingface/facebook/wav2vec2-lv-60-espeak-cv-ft"
        self.transcription_lang = "en"

        # Operation mode
        self.mode = "dictate"  # Default to dictation mode
        self.sigusr1_mode = "dictate"  # Default mode for SIGUSR1 signal
        self.sigusr2_mode = "shell"    # Default mode for SIGUSR2 signal

        # Provider performance controls
        self.enable_reasoning = 'low'
        self.thinking_budget = 128
        self.temperature = 0.2  # Optimal for focused output (2025 best practices)
        self.max_tokens = None  # No output limit by default
        self.top_p = 0.9

        # Microphone release delay
        self.mic_release_delay = 350  # milliseconds

        # Audio validation thresholds
        self.min_recording_duration = 0.7  # seconds
        self.audio_amplitude_threshold = 0.03  # 3% of int16 range
        self.min_peak_duration = 0.5  # seconds (also used as RMS window size)
        self.min_peak_duration_amplitude_threshold = 0.01  # 1% of int16 range for RMS peaks

        # Load environment variables
        script_dir = os.path.dirname(__file__)
        dotenv_path = os.path.join(script_dir, '.env')
        load_dotenv(dotenv_path=dotenv_path)
    
    def load_models_from_file(self, filename):
        """Loads model names from a text file."""
        try:
            script_dir = os.path.dirname(__file__)
            filepath = os.path.join(script_dir, filename)
            with open(filepath, 'r') as f:
                models = [line.strip() for line in f if line.strip()]
            return models
        except FileNotFoundError:
            pr_err(f"Model file '{filename}' not found in '{script_dir}'.")
            return []
        except Exception as e:
            pr_err(f"Error reading model file '{filename}': {e}")
            return []
    
    def select_from_list(self, options, prompt):
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
                pr_notice("Selection cancelled.")
                return None
    
    def is_interactive_mode(self, args_without_script):
        """Determine if running in interactive mode."""
        return len(args_without_script) == 0
    
    def setup_argument_parser(self, composer=None):
        """Setup and return the argument parser."""
        parser = argparse.ArgumentParser(
            description="Real-time dictation using Groq or Gemini.",
            formatter_class=argparse.ArgumentDefaultsHelpFormatter
        )

        # Get available modes dynamically
        available_modes = composer.get_available_modes() if composer else ['dictate']
        parser.add_argument(
            "--provider",
            type=str,
            choices=['groq', 'gemini'],
            default=None,
            help="The transcription provider to use ('groq' or 'gemini')."
        )
        parser.add_argument(
            "--model",
            type=str,
            default=None,
            help="The specific model ID to use for the chosen provider."
        )
        parser.add_argument(
            "--trigger-key",
            type=str,
            default='alt_r',
            help="The key name to trigger recording (e.g., 'alt_r', 'ctrl_r', 'f19'), or 'none' to disable."
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
            default=16000,
            help="Audio sample rate in Hz."
        )
        parser.add_argument(
            "--channels",
            type=int,
            default=1,
            help="Number of audio channels (e.g., 1 for mono)."
        )
        parser.add_argument(
            "--no-trigger-key",
            action="store_true",
            help="Disable keyboard trigger; use POSIX signals (SIGUSR1/SIGUSR2/SIGHUP) instead."
        )
        parser.add_argument(
            "--sigusr1",
            type=str,
            default="dictate",
            dest="sigusr1_mode",
            help="Mode to switch to when SIGUSR1 signal is received (default: dictate)."
        )
        parser.add_argument(
            "--sigusr2",
            type=str,
            default="shell",
            dest="sigusr2_mode",
            help="Mode to switch to when SIGUSR2 signal is received (default: shell)."
        )
        parser.add_argument(
            "-D", "--debug",
            action="count",
            default=0,
            help="Enable debug output: -D (app debug), -DD (app + LiteLLM debug), -DDD (app + LiteLLM + XML stream debug)."
        )
        parser.add_argument(
            "--once",
            action="store_true",
            help="Reset XML state after each response (disables persistent state across transcriptions)."
        )
        parser.add_argument(
            "--xdotool-hz", "--xdotool-cps",
            type=float,
            default=None,
            dest="xdotool_rate",
            help="Set xdotool keystroke rate in Hz/CPS (keystrokes per second)."
        )
        parser.add_argument(
            "--audio-source", "-a",
            type=str,
            choices=['transcribe', 'trans', 'raw'],
            default='raw',
            help="Audio source type: 'transcribe'/'trans' (transcription model processing), 'raw' (direct microphone audio)."
        )
        parser.add_argument(
            "--mode", "-m",
            type=str,
            choices=available_modes,
            default='dictate',
            help=f"Operation mode: {', '.join(available_modes)}."
        )
        parser.add_argument(
            "--transcription-model", "-T",
            type=str,
            default="huggingface/facebook/wav2vec2-lv-60-espeak-cv-ft",
            help="Transcription model specification in format 'provider/model'. Examples: 'huggingface/facebook/wav2vec2-lv-60-espeak-cv-ft', 'openai/whisper-1', 'vosk/path/to/model'."
        )
        parser.add_argument(
            "--transcription-lang", "-L",
            type=str,
            default="en",
            help="Language for transcription (ISO 639-1 code). Examples: 'en', 'es', 'fr'. Only used with Seq2Seq models like Whisper. Defaults to 'en'."
        )
        parser.add_argument(
            "--enable-reasoning",
            type=str,
            choices=['none', 'low', 'medium', 'high'],
            default='low',
            help="Reasoning effort level: 'none' (disabled), 'low' (default), 'medium', 'high' (increases latency)."
        )
        parser.add_argument(
            "--thinking-budget",
            type=int,
            default=128,
            help="Token budget for extended thinking (default: 128, 0 = disabled, must be < max-tokens if specified)."
        )
        parser.add_argument(
            "--temperature",
            type=float,
            default=0.2,
            help="Response randomness (0.0-2.0, lower = more focused, 0.2 optimal for transcription)."
        )
        parser.add_argument(
            "--max-tokens",
            type=int,
            default=None,
            help="Maximum response length in tokens (default: unlimited, use provider's maximum)."
        )
        parser.add_argument(
            "--top-p",
            type=float,
            default=0.9,
            help="Nucleus sampling parameter (0.0-1.0)."
        )
        parser.add_argument(
            "--audio-min-duration",
            type=float,
            default=0.7,
            dest="min_recording_duration",
            help="Minimum recording duration in seconds (default: 0.7)."
        )
        parser.add_argument(
            "--audio-min-amplitude",
            type=float,
            default=0.03,
            dest="audio_amplitude_threshold",
            help="Minimum peak amplitude threshold as fraction of int16 range (default: 0.03 = 3%%)."
        )
        parser.add_argument(
            "--audio-min-rms",
            type=float,
            default=0.01,
            dest="min_peak_duration_amplitude_threshold",
            help="Minimum RMS threshold as fraction of int16 range (default: 0.01 = 1%%). This is the maximum RMS value found across all sliding windows."
        )
        parser.add_argument(
            "--audio-rms-window",
            type=float,
            default=0.5,
            dest="min_peak_duration",
            help="RMS sliding window size in seconds (default: 0.5). Window slides by 1/10th of window size (90%% overlap)."
        )
        parser.add_argument(
            "--key",
            type=str,
            default=None,
            help="API key for the provider (overrides environment variables)."
        )
        parser.add_argument(
            "--mic-release-delay",
            type=int,
            default=350,
            help="Delay in milliseconds to continue recording after trigger release (default: 350ms)."
        )
        return parser
    
    def handle_interactive_mode(self):
        """Handle interactive provider and model selection."""
        print("Running in interactive mode...")

        # Get model ID (require provider/model format)
        print("Enter model in format 'provider/model'")
        print("Examples:")
        print("  openai/gpt-4")
        print("  anthropic/claude-3-5-sonnet-20241022")
        print("  gemini/gemini-2.5-flash")
        print("  groq/llama-3.2-90b-vision-preview")
        self.model_id = input("Model: ").strip()

        if not self.model_id:
            pr_notice("No model specified. Exiting.")
            return False

        if '/' not in self.model_id:
            pr_err(f"Model '{self.model_id}' is malformed. Required format: provider/model")
            return False
        
        return True
    
    def _apply_parsed_args(self, args):
        """Apply parsed arguments to instance variables (single point of truth)."""
        self.language = args.language
        self.sample_rate = args.sample_rate
        self.channels = args.channels
        self.trigger_key_name = args.trigger_key
        if getattr(args, "no_trigger_key", False):
            self.trigger_key_name = "none"
        self.debug_enabled = args.debug >= 1
        self.litellm_debug = args.debug >= 2
        self.xml_stream_debug = args.debug >= 3
        self.xdotool_rate = args.xdotool_rate
        self.reset_state_each_response = getattr(args, 'once', False)

        # Audio source selection
        self.audio_source = getattr(args, 'audio_source', 'raw')

        # Operation mode
        self.mode = getattr(args, 'mode', 'dictate')
        self.sigusr1_mode = getattr(args, 'sigusr1_mode', 'dictate')
        self.sigusr2_mode = getattr(args, 'sigusr2_mode', 'shell')

        # Transcription model configuration
        self.transcription_model = getattr(args, 'transcription_model', self.transcription_model)
        self.transcription_lang = getattr(args, 'transcription_lang', "en")

        # Provider performance controls
        self.enable_reasoning = getattr(args, 'enable_reasoning', 'low')
        self.thinking_budget = getattr(args, 'thinking_budget', 128)
        self.temperature = getattr(args, 'temperature', 0.2)
        self.max_tokens = getattr(args, 'max_tokens', None)
        self.top_p = getattr(args, 'top_p', 0.9)

        # API key
        self.api_key = getattr(args, 'key', None)

        # Microphone release delay
        self.mic_release_delay = getattr(args, 'mic_release_delay', 350)

    def parse_configuration(self):
        """Parse configuration from command line arguments or interactive mode."""
        # Import here to avoid circular dependency
        from instruction_composer import InstructionComposer

        composer = InstructionComposer()
        parser = self.setup_argument_parser(composer)
        args_without_script = sys.argv[1:]
        args = parser.parse_args()

        if self.is_interactive_mode(args_without_script):
            if not self.handle_interactive_mode():
                return False
            # Apply all other args in interactive mode
            self._apply_parsed_args(args)
        else:
            # Non-interactive mode: get model from args
            self.model_id = args.model

            # Extract provider from model_id (format: "provider/model")
            if self.model_id and '/' in self.model_id:
                self.provider = self.model_id.split('/', 1)[0]
            else:
                # Fallback to explicit --provider if model doesn't have prefix
                self.provider = args.provider

            # Apply all other args
            self._apply_parsed_args(args)

            # Validate required model
            if not self.model_id:
                parser.print_help()
                pr_err("--model is required. Format: provider/model (e.g., gemini/gemini-2.5-flash)")
                return False

            # Validate model format
            if '/' not in self.model_id:
                parser.print_help()
                pr_err(f"Model '{self.model_id}' is malformed. Required format: provider/model (e.g., gemini/gemini-2.5-flash)")
                return False

        # Validate transcription-model flag usage
        default_transcription_model = self.__class__().transcription_model
        if self.transcription_model != default_transcription_model:
            if self.audio_source not in ['transcribe', 'trans']:
                parser.print_help()
                pr_err(f"--transcription-model requires --audio-source to be 'transcribe' or 'trans', not '{self.audio_source}'")
                return False

        # Validate audio source requirements
        if self.audio_source in ['transcribe', 'trans']:
            if '/' not in self.transcription_model:
                parser.print_help()
                pr_err(f"Invalid transcription model format: '{self.transcription_model}'. Expected format: provider/model")
                return False

        return True
    
