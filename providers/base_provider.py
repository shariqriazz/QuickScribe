"""
Base provider class with common XML instructions.
"""
from typing import Optional
import numpy as np
import time
import sys
import base64
import io
import soundfile as sf
from .conversation_context import ConversationContext
from .mapper_factory import MapperFactory
from instruction_composer import InstructionComposer


class BaseProvider:
    """Unified provider using LiteLLM abstraction."""

    def __init__(self, config, audio_processor):
        if audio_processor is None:
            raise ValueError("audio_processor is required and cannot be None")

        self.config = config
        self._initialized = False
        self.litellm = None

        # Timing tracking
        self.model_start_time = None
        self.first_response_time = None

        # Cost tracking
        self.total_cost = 0.0

        # Audio processor for instruction injection
        self.audio_processor = audio_processor

        # Instruction composition
        self.instruction_composer = InstructionComposer()

        # Provider extraction (single point of truth)
        self.provider = self._extract_provider(config.model_id)

        # Provider-specific configuration mapper
        self.mapper = MapperFactory.get_mapper(self.provider)

    def _extract_provider(self, model_id: str) -> str:
        """Extract provider from model_id (format: provider/model)."""
        if '/' in model_id:
            return model_id.split('/', 1)[0].lower()
        return ''
    
    def initialize(self) -> bool:
        """Initialize LiteLLM and validate model."""
        try:
            import litellm
            from litellm import exceptions
            self.litellm = litellm
            self.litellm_exceptions = exceptions

            if self.config.litellm_debug:
                litellm._turn_on_debug()

            if self.config.api_key:
                print(f"Using provided API key for {self.provider}")

            print(f"LiteLLM initialized with model: {self.config.model_id}")

            # Validate model with minimal API call
            print("Validating model access...", end=' ', flush=True)
            try:
                completion_params = {
                    "model": self.config.model_id,
                    "messages": [{"role": "user", "content": "test"}],
                    "max_tokens": 1,
                    "stream": False
                }
                if self.config.api_key:
                    completion_params["api_key"] = self.config.api_key

                test_response = self.litellm.completion(**completion_params)
                print("✓")
                self._initialized = True
                return True
            except self.litellm_exceptions.AuthenticationError as e:
                print("✗")
                print(f"Error: Authentication failed for model '{self.config.model_id}'", file=sys.stderr)
                print(f"Check your API key environment variable for this provider", file=sys.stderr)
                return False
            except self.litellm_exceptions.NotFoundError as e:
                print("✗")
                print(f"Error: Model '{self.config.model_id}' not found", file=sys.stderr)
                print(f"Verify the model name and provider prefix are correct", file=sys.stderr)
                return False
            except self.litellm_exceptions.RateLimitError as e:
                print("✗")
                print(f"Error: Rate limit exceeded for model '{self.config.model_id}'", file=sys.stderr)
                return False
            except Exception as e:
                print("✗")
                print(f"Error validating model '{self.config.model_id}': {e}", file=sys.stderr)
                return False

        except ImportError:
            print("Error: litellm library not found. Please install it: pip install litellm", file=sys.stderr)
            return False
        except Exception as e:
            print(f"Error initializing LiteLLM: {e}", file=sys.stderr)
            return False

    def is_initialized(self) -> bool:
        """Check if provider is initialized."""
        return self._initialized and self.litellm is not None

    def _encode_audio_to_base64(self, audio_np: np.ndarray, sample_rate: int) -> str:
        """Encode audio numpy array to base64 WAV string."""
        wav_bytes_io = io.BytesIO()
        sf.write(wav_bytes_io, audio_np, sample_rate, format='WAV', subtype='PCM_16')
        wav_bytes = wav_bytes_io.getvalue()
        wav_bytes_io.close()
        return base64.b64encode(wav_bytes).decode('utf-8')

    def _build_prompt(self, context: ConversationContext) -> str:
        """Build prompt from XML instructions and conversation context."""
        xml_instructions = self.get_xml_instructions()
        prompt = xml_instructions

        if context.xml_markup:
            prompt += f"\n\nCurrent conversation XML: {context.xml_markup}"
            prompt += f"\nCurrent conversation text: {context.compiled_text}"

        return prompt

    def _process_streaming_response(self, response, streaming_callback=None, final_callback=None):
        """Process streaming response chunks from LiteLLM completion."""
        print("\nRECEIVED FROM MODEL (streaming):")
        accumulated_text = ""
        usage_data = None
        last_chunk = None
        reasoning_header_shown = False
        thinking_header_shown = False
        output_header_shown = False

        for chunk in response:
            last_chunk = chunk
            delta = chunk.choices[0].delta

            # Display reasoning content (extended thinking)
            if hasattr(delta, 'reasoning_content') and delta.reasoning_content is not None:
                if not reasoning_header_shown:
                    print("\n[REASONING]")
                    reasoning_header_shown = True
                print(delta.reasoning_content, end='', flush=True)

            # Display thinking blocks (Anthropic-specific)
            if hasattr(delta, 'thinking_blocks') and delta.thinking_blocks is not None:
                if not thinking_header_shown:
                    print("\n[THINKING]")
                    thinking_header_shown = True
                for block in delta.thinking_blocks:
                    if 'thinking' in block:
                        print(block['thinking'], end='', flush=True)

            if delta.content is not None:
                if not output_header_shown:
                    print("\n[OUTPUT]")
                    output_header_shown = True
                chunk_text = delta.content
                self.mark_first_response()
                if streaming_callback:
                    streaming_callback(chunk_text)
                accumulated_text += chunk_text

            # Capture usage data from final chunk
            if hasattr(chunk, 'usage') and chunk.usage is not None:
                usage_data = chunk.usage

        # Print timing after streaming completes
        self._print_timing_stats()

        # Display cache statistics and cost
        if usage_data:
            self._display_cache_stats(usage_data, completion_response=last_chunk)

        if final_callback:
            final_callback(accumulated_text)

    def transcribe(self, context: ConversationContext,
                   audio_data: Optional[np.ndarray] = None,
                   text_data: Optional[str] = None,
                   streaming_callback=None,
                   final_callback=None) -> None:
        """
        Unified transcription interface for both audio and text inputs.

        Args:
            context: Conversation context with XML markup and compiled text
            audio_data: Optional audio data as numpy array
            text_data: Optional pre-transcribed text
            streaming_callback: Optional callback for streaming text chunks
            final_callback: Optional callback for final result
        """
        if not self.is_initialized():
            print("\nError: Provider not initialized.", file=sys.stderr)
            return

        try:
            # Get instructions (includes audio processor if set)
            xml_instructions = self.get_xml_instructions()

            # System message: Static instructions (cached)
            system_content = {"type": "text", "text": xml_instructions}

            if self.provider == 'anthropic':
                system_content["cache_control"] = {"type": "ephemeral"}

            system_message = {
                "role": "system",
                "content": [system_content]
            }

            # Build user content based on input type
            if audio_data is not None:
                # Audio input
                audio_b64 = self._encode_audio_to_base64(audio_data, context.sample_rate)
                user_content = []

                if context.xml_markup:
                    context_text = f"Current conversation XML: {context.xml_markup}"
                    context_text += f"\nCurrent conversation text: {context.compiled_text}"
                    user_content.append({"type": "text", "text": context_text})
                else:
                    context_text = "CRITICAL: No prior conversation. There is nothing to modify. ALL input must be treated as DICTATION. Transcribe according to system instructions (append with incrementing IDs starting from 10)."
                    user_content.append({"type": "text", "text": context_text})

                user_content.append({"type": "input_audio", "input_audio": {"data": audio_b64, "format": "wav"}})
            else:
                # Text input
                user_text = ""

                if context.xml_markup:
                    user_text += f"Current conversation XML: {context.xml_markup}"
                    user_text += f"\nCurrent conversation text: {context.compiled_text}"
                    user_text += "\n\n"
                else:
                    user_text += "CRITICAL: No prior conversation. There is nothing to modify. ALL input must be treated as DICTATION. Transcribe according to system instructions (append with incrementing IDs starting from 10).\n\n"

                user_text += f"NEW INPUT (requires processing):"
                user_text += f"\nMechanical transcription: {text_data}"
                user_text += "\n\nCRITICAL: The 'mechanical transcription' above is raw output from automatic speech recognition. It requires the SAME analysis as audio input:"
                user_text += "\n- Treat as if you just heard the audio yourself"
                user_text += "\n- Identify sound-alike errors: \"there/their\", \"to/too\", \"no/know\", etc."
                user_text += "\n- Fix misrecognized words based on context"
                user_text += "\n- Apply ALL copy editing and formatting rules"
                user_text += "\n- Handle false starts, fillers, and speech patterns"
                user_text += "\n- Generate TX (literal with sound-alike options), INT (clean edited), UPDATE (XML tags)"

                user_content = user_text

            messages = [
                system_message,
                {"role": "user", "content": user_content}
            ]

            # Display what's being sent
            self._display_user_content(user_content)
            self.start_model_timer()

            # Call LiteLLM
            completion_params = {
                "model": self.config.model_id,
                "messages": messages,
                "stream": True,
                "stream_options": {"include_usage": True},
                "temperature": self.config.temperature
            }

            if self.config.max_tokens is not None:
                completion_params["max_tokens"] = self.config.max_tokens

            if self.config.api_key:
                completion_params["api_key"] = self.config.api_key

            # Map reasoning parameters via provider-specific mapper
            reasoning_params = self.mapper.map_reasoning_params(
                self.config.enable_reasoning,
                self.config.thinking_budget
            )
            completion_params.update(reasoning_params)

            response = self.litellm.completion(**completion_params)

            self._process_streaming_response(response, streaming_callback, final_callback)

        except Exception as e:
            operation = "audio transcription" if audio_data is not None else "text processing"
            self._handle_provider_error(e, operation)
    
    def get_xml_instructions(self) -> str:
        """Get the composed XML instructions from files."""
        # Determine audio source name for instruction loading
        audio_source_name = None
        if self.config.audio_source in ['phoneme', 'wav2vec']:
            audio_source_name = 'wav2vec2'

        # Compose instructions from files (reads current mode from config)
        instructions = self.instruction_composer.compose(
            self.config.mode,
            audio_source_name,
            self.provider
        )

        return instructions


    def start_model_timer(self):
        """Mark the start of model processing for timing measurements."""
        self.model_start_time = time.time()
        self.first_response_time = None  # Reset for new request

    def mark_first_response(self):
        """Mark when the first response chunk is received."""
        if self.first_response_time is None:
            self.first_response_time = time.time()

    def _print_timing_stats(self):
        """Print timing statistics."""
        if self.model_start_time and self.first_response_time:
            model_time = self.first_response_time - self.model_start_time
            print(f"\n🚀 Model processing time: {model_time:.3f}s")

    def _handle_provider_error(self, error: Exception, operation: str) -> None:
        """Common error handling for provider operations with full error details."""
        import traceback

        # Print full error details for debugging
        print(f"\n❌ ERROR during {operation}:", file=sys.stderr)
        print(f"Error Type: {type(error).__name__}", file=sys.stderr)
        print(f"Error Message: {str(error)}", file=sys.stderr)

        if hasattr(self, 'google_exceptions'):
            # Gemini-specific errors
            if isinstance(error, self.google_exceptions.InvalidArgument):
                print(f"Gemini API Error (Invalid Argument) - check your request parameters", file=sys.stderr)
            elif isinstance(error, self.google_exceptions.PermissionDenied):
                print(f"Gemini API Error (Permission Denied) - check your API key and permissions", file=sys.stderr)
            elif isinstance(error, self.google_exceptions.ResourceExhausted):
                print(f"Gemini API Error (Rate Limit/Quota) - you may have exceeded usage limits", file=sys.stderr)
            else:
                print(f"Gemini API Error - see details above", file=sys.stderr)
        elif hasattr(self, 'GroqError'):
            # Groq-specific errors
            if isinstance(error, self.GroqError):
                print(f"Groq API Error - see details above", file=sys.stderr)
            else:
                print(f"Groq Provider Error - see details above", file=sys.stderr)
        else:
            print(f"Provider Error - see details above", file=sys.stderr)

        # Print stack trace for debugging
        print(f"Stack trace:", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)

    def _display_cache_stats(self, usage_data, completion_response=None) -> None:
        """Display cache statistics and cost from usage data."""
        if not self.config.debug_enabled:
            return

        print("\n" + "-" * 60)
        print("USAGE STATISTICS:")

        # Standard token counts
        if hasattr(usage_data, 'prompt_tokens'):
            print(f"  Prompt tokens: {usage_data.prompt_tokens}")
        if hasattr(usage_data, 'completion_tokens'):
            print(f"  Completion tokens: {usage_data.completion_tokens}")
        if hasattr(usage_data, 'total_tokens'):
            print(f"  Total tokens: {usage_data.total_tokens}")

        # Anthropic-specific cache fields
        if hasattr(usage_data, 'cache_creation_input_tokens') and usage_data.cache_creation_input_tokens:
            print(f"  Cache creation tokens: {usage_data.cache_creation_input_tokens} (Anthropic: written to cache)")

        if hasattr(usage_data, 'cache_read_input_tokens') and usage_data.cache_read_input_tokens:
            print(f"  Cache read tokens: {usage_data.cache_read_input_tokens} (Anthropic: read from cache)")

        # DeepSeek-specific cache fields
        if hasattr(usage_data, 'prompt_cache_hit_tokens') and usage_data.prompt_cache_hit_tokens:
            print(f"  Cache hit tokens: {usage_data.prompt_cache_hit_tokens} (DeepSeek: cache hits)")

        if hasattr(usage_data, 'prompt_cache_miss_tokens') and usage_data.prompt_cache_miss_tokens:
            print(f"  Cache miss tokens: {usage_data.prompt_cache_miss_tokens} (DeepSeek: cache misses)")

        # OpenAI/Gemini format: prompt_tokens_details
        if hasattr(usage_data, 'prompt_tokens_details') and usage_data.prompt_tokens_details:
            details = usage_data.prompt_tokens_details

            # Show audio tokens if present
            if hasattr(details, 'audio_tokens') and details.audio_tokens:
                print(f"  Audio tokens: {details.audio_tokens}")

            # Show text tokens if present
            if hasattr(details, 'text_tokens') and details.text_tokens:
                print(f"  Text tokens: {details.text_tokens}")

            # Show cached tokens (None = no caching, 0 = cache warming, >0 = cache hit)
            if hasattr(details, 'cached_tokens'):
                if details.cached_tokens is None:
                    print(f"  Cached tokens: None (no implicit caching detected)")
                elif details.cached_tokens == 0:
                    print(f"  Cached tokens: 0 (cache warming - first request)")
                else:
                    print(f"  Cached tokens: {details.cached_tokens} (cache hit!)")

        # Completion token details
        if hasattr(usage_data, 'completion_tokens_details') and usage_data.completion_tokens_details:
            details = usage_data.completion_tokens_details

            # Show reasoning tokens if present (extended thinking)
            if hasattr(details, 'reasoning_tokens') and details.reasoning_tokens:
                print(f"  Reasoning tokens: {details.reasoning_tokens} (extended thinking)")

        # Gemini-specific: cached_content_token_count (alternative field)
        if hasattr(usage_data, 'cached_content_token_count') and usage_data.cached_content_token_count:
            print(f"  Cached content tokens: {usage_data.cached_content_token_count} (Gemini: implicit cache)")

        # Calculate and display cost
        if completion_response:
            try:
                current_cost = self.litellm.completion_cost(completion_response=completion_response)
                self.total_cost += current_cost
                print(f"\nCOST:")
                print(f"  Current request: ${current_cost:.6f}")
                print(f"  Total session: ${self.total_cost:.6f}")
            except Exception as e:
                print(f"\nCOST: Unable to calculate ({str(e)})")

        print("-" * 60)

    def _display_user_content(self, user_content):
        """Display user content being sent to model."""
        print("\n" + "="*60)
        print("SENDING TO MODEL:")

        # Handle list format (audio transcription)
        if isinstance(user_content, list):
            for content_block in user_content:
                if content_block["type"] == "text":
                    print(content_block["text"])
                elif content_block["type"] == "input_audio":
                    print("Audio: audio_data.wav (base64)")
        # Handle string format (text transcription)
        else:
            print(user_content)

        print("-" * 60)

    def _get_generation_config(self) -> dict:
        """Get provider-agnostic generation configuration."""
        config = {
            'temperature': self.config.temperature,
            'enable_reasoning': self.config.enable_reasoning,
            'response_format': 'text'
        }

        if self.config.max_tokens is not None:
            config['max_output_tokens'] = self.config.max_tokens

        # top_p not included - using default to avoid conflicting with temperature

        return config
