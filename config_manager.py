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
        self.debug_enabled = False
        self.no_trigger_key = False
        self.xdotool_rate = None
        self.reset_state_each_response = False

        # API key configuration
        self.api_key = None

        # VOSK configuration
        self.vosk_model_path = None
        self.vosk_lgraph_path = None

        # Audio source configuration
        self.audio_source = "raw"  # Default to raw microphone

        # Wav2Vec2 configuration
        self.wav2vec2_model_path = "facebook/wav2vec2-lv-60-espeak-cv-ft"  # Default phoneme model

        # Provider performance controls
        self.enable_reasoning = 'none'
        self.thinking_budget = 0
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
        return len(args_without_script) == 0
    
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
            type=str,
            choices=['none', 'low', 'medium', 'high'],
            default='none',
            help="Reasoning effort level: 'none' (disabled, default for low latency), 'low', 'medium', 'high' (increases latency)."
        )
        parser.add_argument(
            "--thinking-budget",
            type=int,
            default=0,
            help="Token budget for extended thinking (0 = disabled, must be < max-tokens if specified)."
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
            "--key",
            type=str,
            default=None,
            help="API key for the provider (overrides environment variables)."
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
            print("No model specified. Exiting.")
            return False

        if '/' not in self.model_id:
            print(f"Error: Model '{self.model_id}' is malformed. Required format: provider/model", file=sys.stderr)
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
        self.debug_enabled = args.debug
        self.xdotool_rate = args.xdotool_rate
        self.reset_state_each_response = getattr(args, 'once', False)

        # Audio source selection
        self.audio_source = getattr(args, 'audio_source', 'raw')

        # VOSK configuration
        self.vosk_model_path = getattr(args, 'vosk_model', None)
        self.vosk_lgraph_path = getattr(args, 'vosk_lgraph', None)
        # Wav2Vec2 configuration
        self.wav2vec2_model_path = getattr(args, 'wav2vec2_model', self.wav2vec2_model_path)

        # Provider performance controls
        self.enable_reasoning = getattr(args, 'enable_reasoning', 'none')
        self.thinking_budget = getattr(args, 'thinking_budget', 0)
        self.temperature = getattr(args, 'temperature', 0.2)
        self.max_tokens = getattr(args, 'max_tokens', None)
        self.top_p = getattr(args, 'top_p', 0.9)

        # API key
        self.api_key = getattr(args, 'key', None)

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
                print("\nError: --model is required. Format: provider/model (e.g., gemini/gemini-2.5-flash)", file=sys.stderr)
                return False

            # Validate model format
            if '/' not in self.model_id:
                parser.print_help()
                print(f"\nError: Model '{self.model_id}' is malformed. Required format: provider/model (e.g., gemini/gemini-2.5-flash)", file=sys.stderr)
                return False

        # Validate audio source requirements
        if self.audio_source == 'vosk' and not self.vosk_model_path:
            parser.print_help()
            print("\nError: --vosk-model is required when --audio-source is 'vosk'", file=sys.stderr)
            return False

        if self.audio_source == 'wav2vec' and not self.wav2vec2_model_path:
            parser.print_help()
            print("\nError: --wav2vec2-model is required when --audio-source is 'wav2vec'", file=sys.stderr)
            return False

        return True
    
