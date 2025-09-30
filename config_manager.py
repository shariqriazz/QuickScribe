import os
import sys
import argparse
from dotenv import load_dotenv


class ConfigManager:
    """Manages configuration, argument parsing, and interactive model selection for dictation."""
    
    def __init__(self):
        self.provider = None
        self.model_id = None
        self.language = None
        self.sample_rate = 16000
        self.channels = 1
        self.trigger_key_name = 'alt_r'
        self.use_xdotool = False
        self.debug_enabled = False
        self.no_trigger_key = False
        self.xdotool_rate = None

        # VOSK configuration
        self.vosk_model_path = None
        self.vosk_lgraph_path = None

        # Audio source configuration
        self.audio_source = "raw"  # Default to raw microphone

        # Wav2Vec2 configuration
        self.wav2vec2_model_path = "facebook/wav2vec2-lv-60-espeak-cv-ft"  # Default phoneme model

        # Provider performance controls
        self.enable_reasoning = False
        self.temperature = 0.2  # Optimal for focused output (2025 best practices)
        self.max_tokens = None  # No output limit by default
        self.top_p = 0.9
        
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
            print(f"Error: Model file '{filename}' not found in '{script_dir}'.", file=sys.stderr)
            return []
        except Exception as e:
            print(f"Error reading model file '{filename}': {e}", file=sys.stderr)
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
                print("\nSelection cancelled.")
                return None
    
    def is_interactive_mode(self, args_without_script):
        """Determine if running in interactive mode."""
        return (len(args_without_script) == 0 or 
                (len(args_without_script) == 1 and args_without_script[0] == '--use-xdotool'))
    
    def setup_argument_parser(self):
        """Setup and return the argument parser."""
        parser = argparse.ArgumentParser(
            description="Real-time dictation using Groq or Gemini.",
            formatter_class=argparse.ArgumentDefaultsHelpFormatter
        )
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
            "--use-xdotool",
            action="store_true",
            help="Use xdotool for typing text instead of clipboard paste. Linux only."
        )
        parser.add_argument(
            "--no-trigger-key",
            action="store_true",
            help="Disable keyboard trigger; use POSIX signals (SIGUSR1/SIGUSR2) instead."
        )
        parser.add_argument(
            "-D", "--debug",
            action="store_true",
            help="Enable debug output (shows XML processing details after streaming completes)."
        )
        parser.add_argument(
            "--xdotool-hz", "--xdotool-cps",
            type=float,
            default=None,
            dest="xdotool_rate",
            help="Set xdotool keystroke rate in Hz/CPS (keystrokes per second)."
        )
        parser.add_argument(
            "--vosk-model",
            type=str,
            default=None,
            help="Path to VOSK model directory (required for VOSK provider)."
        )
        parser.add_argument(
            "--vosk-lgraph",
            type=str,
            default=None,
            help="Path to VOSK L-graph file for grammar-constrained recognition."
        )
        parser.add_argument(
            "--audio-source", "-a",
            type=str,
            choices=['vosk', 'phoneme', 'wav2vec', 'raw'],
            default='raw',
            help="Audio source type: 'vosk' (VOSK speech recognition), 'phoneme'/'wav2vec' (Wav2Vec2 phoneme recognition), 'raw' (direct microphone)."
        )
        parser.add_argument(
            "--wav2vec2-model",
            type=str,
            default="facebook/wav2vec2-lv-60-espeak-cv-ft",
            help="Path or model ID for Wav2Vec2 phoneme recognition model. Default: facebook/wav2vec2-lv-60-espeak-cv-ft (automatically downloaded from Hugging Face)."
        )
        parser.add_argument(
            "--enable-reasoning",
            action="store_true",
            help="Enable reasoning/chain-of-thought in AI models (increases latency)."
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
        return parser
    
    def handle_interactive_mode(self):
        """Handle interactive provider and model selection."""
        print("Running in interactive mode...")
        groq_key_present = bool(os.getenv("GROQ_API_KEY"))
        gemini_key_present = bool(os.getenv("GOOGLE_API_KEY"))

        if groq_key_present:
            print("Found GROQ_API_KEY in .env, selecting Groq as provider.")
            self.provider = 'groq'
        elif gemini_key_present:
            print("Found GOOGLE_API_KEY in .env (but no Groq key), selecting Gemini as provider.")
            self.provider = 'gemini'
        else:
            print("No API keys found in .env.")
            self.provider = self.select_from_list(['groq', 'gemini'], "Select a provider:")
            if not self.provider:
                print("No provider selected. Exiting.")
                return False

        # Select Model based on Provider
        if self.provider == 'groq':
            available_models = self.load_models_from_file("groq_models.txt")
            if not available_models:
                print("Could not load Groq models. Please ensure 'groq_models.txt' exists.", file=sys.stderr)
                return False
            self.model_id = self.select_from_list(available_models, f"Select a Groq model:")
        elif self.provider == 'gemini':
            available_models = self.load_models_from_file("gemini_models.txt")
            if not available_models:
                print("Could not load Gemini models. Please ensure 'gemini_models.txt' exists.", file=sys.stderr)
                return False
            self.model_id = self.select_from_list(available_models, f"Select a Gemini model:")

        if not self.model_id:
            print("No model selected. Exiting.")
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
        self.use_xdotool = args.use_xdotool
        self.debug_enabled = args.debug
        self.xdotool_rate = args.xdotool_rate

        # Audio source selection
        self.audio_source = getattr(args, 'audio_source', 'raw')

        # VOSK configuration
        self.vosk_model_path = getattr(args, 'vosk_model', None)
        self.vosk_lgraph_path = getattr(args, 'vosk_lgraph', None)
        # Wav2Vec2 configuration
        self.wav2vec2_model_path = getattr(args, 'wav2vec2_model', self.wav2vec2_model_path)

        # Provider performance controls
        self.enable_reasoning = getattr(args, 'enable_reasoning', False)
        self.temperature = getattr(args, 'temperature', 0.2)
        self.max_tokens = getattr(args, 'max_tokens', None)
        self.top_p = getattr(args, 'top_p', 0.9)

    def parse_configuration(self):
        """Parse configuration from command line arguments or interactive mode."""
        parser = self.setup_argument_parser()
        args_without_script = sys.argv[1:]
        args = parser.parse_args()

        if self.is_interactive_mode(args_without_script):
            if not self.handle_interactive_mode():
                return False
            # Apply all other args in interactive mode
            self._apply_parsed_args(args)
        else:
            # Non-interactive mode: get provider/model from args
            self.provider = args.provider
            self.model_id = args.model
            # Apply all other args
            self._apply_parsed_args(args)

            # Validate required args if not interactive
            if not self.provider or not self.model_id:
                parser.print_help()
                print("\nError: --provider and --model are required when running with arguments.", file=sys.stderr)
                return False

        return True
    
