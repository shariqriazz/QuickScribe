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
from lib.pr_log import (
    pr_emerg, pr_alert, pr_crit, pr_err, pr_warn, pr_notice, pr_info, pr_debug,
    get_streaming_handler
)


class TerminateStream(Exception):
    """Signal to terminate streaming when </xml> tag is detected."""
    pass


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

        # Route extraction (format: provider/model@route)
        if '@' in config.model_id:
            model_parts = config.model_id.split('@', 1)
            self.model_without_route: str = model_parts[0]
            self.route: Optional[str] = model_parts[1]
        else:
            self.model_without_route: str = config.model_id
            self.route: Optional[str] = None

        # Provider extraction (single point of truth)
        self.provider = self._extract_provider(self.model_without_route)

        # Provider-specific configuration mapper
        self.mapper = MapperFactory.get_mapper(self.provider)

        # Validation results (populated after initialize)
        self._validation_results = None

    def _extract_provider(self, model_without_route: str) -> str:
        """Extract provider from model (format: provider/model)."""
        if '/' in model_without_route:
            return model_without_route.split('/', 1)[0].lower()
        return ''

    def _run_validation_tests(self, test_audio_silence_b64: str, sumtest_audio_b64: str):
        """
        Run parallel validation tests with intelligence checking.

        Args:
            test_audio_silence_b64: Base64 encoded silent audio
            sumtest_audio_b64: Base64 encoded sumtest.wav audio

        Returns:
            dict: Validation results with keys: overall_success, text_passed, text_error,
                  text_response, audio_passed, audio_error, audio_response, combined1_passed,
                  combined1_error, combined1_response, combined2_passed, combined2_error, combined2_response
        """
        import concurrent.futures
        import re

        text_error = None
        text_response = None
        audio_error = None
        audio_response = None
        combined1_error = None
        combined1_response = None
        combined2_error = None
        combined2_response = None

        def test_text():
            completion_params = {
                "model": self.model_without_route,
                "messages": [{"role": "user", "content": "1 + 1 compute exactly only provide answer"}],
                "max_tokens": 512,
                "stream": False
            }
            if self.route:
                completion_params["route"] = self.route
            if self.config.api_key:
                completion_params["api_key"] = self.config.api_key
            return self.litellm.completion(**completion_params)

        def test_audio():
            audio_content = self.mapper.map_audio_params(sumtest_audio_b64, "wav")
            completion_params = {
                "model": self.model_without_route,
                "messages": [{"role": "user", "content": [audio_content]}],
                "max_tokens": 512,
                "stream": False
            }
            if self.route:
                completion_params["route"] = self.route
            if self.config.api_key:
                completion_params["api_key"] = self.config.api_key
            return self.litellm.completion(**completion_params)

        def test_combined1_text_with_silence():
            audio_content = self.mapper.map_audio_params(test_audio_silence_b64, "wav")
            completion_params = {
                "model": self.model_without_route,
                "messages": [{"role": "user", "content": [
                    {"type": "text", "text": "1 + 1 compute exactly only provide answer"},
                    audio_content
                ]}],
                "max_tokens": 512,
                "stream": False
            }
            if self.route:
                completion_params["route"] = self.route
            if self.config.api_key:
                completion_params["api_key"] = self.config.api_key
            return self.litellm.completion(**completion_params)

        def test_combined2_audio_with_prompt():
            audio_content = self.mapper.map_audio_params(sumtest_audio_b64, "wav")
            completion_params = {
                "model": self.model_without_route,
                "messages": [{"role": "user", "content": [
                    {"type": "text", "text": "compute value"},
                    audio_content
                ]}],
                "max_tokens": 512,
                "stream": False
            }
            if self.route:
                completion_params["route"] = self.route
            if self.config.api_key:
                completion_params["api_key"] = self.config.api_key
            return self.litellm.completion(**completion_params)

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            text_future = executor.submit(test_text)
            audio_future = executor.submit(test_audio)
            combined1_future = executor.submit(test_combined1_text_with_silence)
            combined2_future = executor.submit(test_combined2_audio_with_prompt)

            try:
                text_result = text_future.result()
                text_response = text_result.choices[0].message.content
                pr_debug(f"text_response raw: {repr(text_response)}")
                if text_response is None:
                    text_response = ""
                else:
                    text_response = text_response.strip()
                pr_debug(f"text_response stripped: {repr(text_response)}")
            except Exception as e:
                text_error = e
                pr_debug(f"text_error: {e}")

            try:
                audio_result = audio_future.result()
                audio_response = audio_result.choices[0].message.content
                pr_debug(f"audio_response raw: {repr(audio_response)}")

                # Check for reasoning_content if main content is empty/minimal
                if not audio_response or len(audio_response.strip()) < 3:
                    reasoning = getattr(audio_result.choices[0].message, 'reasoning_content', None)
                    if reasoning:
                        pr_debug(f"audio reasoning_content found: {repr(reasoning[:100])}")
                        audio_response = reasoning

                if audio_response is None:
                    audio_response = ""
                else:
                    audio_response = audio_response.strip()
                pr_debug(f"audio_response stripped: {repr(audio_response)}")
            except Exception as e:
                audio_error = e
                pr_debug(f"audio_error: {e}")

            try:
                combined1_result = combined1_future.result()
                combined1_response = combined1_result.choices[0].message.content
                pr_debug(f"combined1_response raw: {repr(combined1_response)}")
                if combined1_response is None:
                    combined1_response = ""
                else:
                    combined1_response = combined1_response.strip()
                pr_debug(f"combined1_response stripped: {repr(combined1_response)}")
            except Exception as e:
                combined1_error = e
                pr_debug(f"combined1_error: {e}")

            try:
                combined2_result = combined2_future.result()
                combined2_response = combined2_result.choices[0].message.content
                pr_debug(f"combined2_response raw: {repr(combined2_response)}")
                if combined2_response is None:
                    combined2_response = ""
                else:
                    combined2_response = combined2_response.strip()
                pr_debug(f"combined2_response stripped: {repr(combined2_response)}")
            except Exception as e:
                combined2_error = e
                pr_debug(f"combined2_error: {e}")

        def check_intelligence(response):
            if response and re.search(r'\b2\b|two', response, re.IGNORECASE):
                return True
            return False

        # For raw audio source, allow text-only failure if audio tests pass
        audio_only_passed = (audio_error is None and combined1_error is None and combined2_error is None)
        all_passed = (text_error is None and audio_error is None and
                     combined1_error is None and combined2_error is None)

        # Determine overall success
        overall_success = all_passed or (self.config.audio_source == 'raw' and audio_only_passed)

        from lib.pr_log import pr_info, pr_warn, pr_err

        # Helper to format response for display (replace newlines with space)
        def format_response(resp):
            if resp:
                return resp.replace('\n', ' ').replace('\r', ' ')
            return resp

        if text_error is None:
            pr_info("Text validation: ✓")
            if check_intelligence(text_response):
                pr_info(f"Text intelligence test: ✓ Got: {format_response(text_response)}")
            else:
                pr_warn(f"Text intelligence test: ⚠ Expected '2' but got: {format_response(text_response)}")
        else:
            pr_err(f"Text validation failed: {text_error}")

        if audio_error is None:
            pr_info("Audio validation: ✓")
            if check_intelligence(audio_response):
                pr_info(f"Audio intelligence test: ✓ Got: {format_response(audio_response)}")
            else:
                pr_warn(f"Audio intelligence test: ⚠ Expected '2' but got: {format_response(audio_response)}")
        else:
            pr_err(f"Audio validation failed: {audio_error}")

        if combined1_error is None:
            pr_info("Combined (text+silence) validation: ✓")
            if check_intelligence(combined1_response):
                pr_info(f"Combined (text+silence) intelligence test: ✓ Got: {format_response(combined1_response)}")
            else:
                pr_warn(f"Combined (text+silence) intelligence test: ⚠ Expected '2' but got: {format_response(combined1_response)}")
        else:
            pr_err(f"Combined (text+silence) validation failed: {combined1_error}")

        if combined2_error is None:
            pr_info("Combined (audio+prompt) validation: ✓")
            if check_intelligence(combined2_response):
                pr_info(f"Combined (audio+prompt) intelligence test: ✓ Got: {format_response(combined2_response)}")
            else:
                pr_warn(f"Combined (audio+prompt) intelligence test: ⚠ Expected '2' but got: {format_response(combined2_response)}")
        else:
            pr_err(f"Combined (audio+prompt) validation failed: {combined2_error}")

        # Print overall validation result
        if overall_success:
            pr_info("Model validation complete: ✓")
            self._initialized = True
        else:
            pr_err("Model validation failed: ✗")

        # Return structured results dict
        return {
            'overall_success': overall_success,
            'text_passed': text_error is None,
            'text_error': str(text_error) if text_error else None,
            'text_response': text_response,
            'audio_passed': audio_error is None,
            'audio_error': str(audio_error) if audio_error else None,
            'audio_response': audio_response,
            'combined1_passed': combined1_error is None,
            'combined1_error': str(combined1_error) if combined1_error else None,
            'combined1_response': combined1_response,
            'combined2_passed': combined2_error is None,
            'combined2_error': str(combined2_error) if combined2_error else None,
            'combined2_response': combined2_response
        }
    
    def initialize(self) -> bool:
        """Initialize LiteLLM and validate model."""
        try:
            import litellm
            from litellm import exceptions
            self.litellm = litellm
            self.litellm_exceptions = exceptions

            if self.config.litellm_debug:
                pr_debug("Enabling LiteLLM debug logging")
                litellm._turn_on_debug()

            if self.config.api_key:
                pr_info(f"Using provided API key for {self.provider}")

            pr_info(f"LiteLLM initialized with model: {self.config.model_id}")

            # Skip validation for transcription-only models
            if self.mapper.uses_transcription_endpoint(self.model_without_route):
                pr_info("Skipping validation for transcription-only model")
                self._initialized = True
                return True

            # Skip validation when using local transcription
            if self.config.audio_source in ['transcribe', 'trans']:
                pr_info("Skipping validation when using local transcription")
                self._initialized = True
                return True

            # Generate minimal test audio (0.1 second silence)
            test_audio_silence = np.zeros(int(0.1 * self.config.sample_rate), dtype=np.int16)
            test_audio_silence_b64 = self._encode_audio_to_base64(test_audio_silence, self.config.sample_rate)

            # Load sumtest.wav for audio intelligence test
            import os
            sumtest_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'samples', 'sumtest.wav')
            sumtest_audio, sumtest_sr = sf.read(sumtest_path)
            if sumtest_audio.dtype != np.int16:
                sumtest_audio = (sumtest_audio * 32767).astype(np.int16)
            sumtest_audio_b64 = self._encode_audio_to_base64(sumtest_audio, sumtest_sr)

            # Validate model with parallel intelligence tests
            pr_info("Validating model access...")
            try:
                self._validation_results = self._run_validation_tests(test_audio_silence_b64, sumtest_audio_b64)
                return self._validation_results['overall_success']

            except self.litellm_exceptions.AuthenticationError as e:
                pr_crit("Model validation failed: ✗")
                pr_err(f"Authentication failed for model '{self.config.model_id}'")
                pr_err(f"Check your API key environment variable for this provider")
                return False
            except self.litellm_exceptions.NotFoundError as e:
                pr_crit("Model validation failed: ✗")
                pr_err(f"Model '{self.config.model_id}' not found")
                pr_err(f"Verify the model name and provider prefix are correct")
                return False
            except self.litellm_exceptions.RateLimitError as e:
                pr_crit("Model validation failed: ✗")
                pr_err(f"Rate limit exceeded for model '{self.config.model_id}'")
                return False
            except Exception as e:
                pr_crit("Model validation failed: ✗")
                pr_err(f"Error validating model '{self.config.model_id}': {e}")
                return False

        except ImportError:
            pr_alert("litellm library not found. Please install it: pip install litellm")
            return False
        except Exception as e:
            pr_err(f"Error initializing LiteLLM: {e}")
            return False

    def is_initialized(self) -> bool:
        """Check if provider is initialized."""
        return self._initialized and self.litellm is not None

    @property
    def validation_results(self) -> Optional[dict]:
        """Get validation test results from initialization."""
        return self._validation_results

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
        pr_info("RECEIVED FROM MODEL (streaming):")
        accumulated_text = ""
        usage_data = None
        last_chunk = None
        reasoning_header_shown = False
        thinking_header_shown = False
        output_header_shown = False

        try:
            with get_streaming_handler() as stream:
                for chunk in response:
                    last_chunk = chunk
                    delta = chunk.choices[0].delta

                    if hasattr(delta, 'reasoning_content') and delta.reasoning_content is not None:
                        if not reasoning_header_shown:
                            pr_notice("[REASONING]")
                            reasoning_header_shown = True
                        stream.write(delta.reasoning_content)

                    if hasattr(delta, 'thinking_blocks') and delta.thinking_blocks is not None:
                        if not thinking_header_shown:
                            pr_notice("[THINKING]")
                            thinking_header_shown = True
                        for block in delta.thinking_blocks:
                            if 'thinking' in block:
                                stream.write(block['thinking'])

                    if delta.content is not None:
                        if not output_header_shown:
                            pr_notice("[OUTPUT]")
                            output_header_shown = True
                        chunk_text = delta.content
                        self.mark_first_response()
                        stream.write(chunk_text)
                        if streaming_callback:
                            streaming_callback(chunk_text)
                        accumulated_text += chunk_text

                        if '</xml>' in accumulated_text:
                            raise TerminateStream()

                    if hasattr(chunk, 'usage') and chunk.usage is not None:
                        usage_data = chunk.usage

        except TerminateStream:
            if hasattr(response, 'completion_stream') and hasattr(response.completion_stream, 'close'):
                response.completion_stream.close()
            pr_debug("Stream terminated: </xml> tag detected")

        self._print_timing_stats()

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
            pr_err("Provider not initialized.")
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
                "model": self.model_without_route,
                "messages": messages,
                "stream": True,
                "stream_options": {"include_usage": True},
                "temperature": self.config.temperature
            }

            if self.route:
                completion_params["route"] = self.route

            if self.config.max_tokens is not None:
                completion_params["max_tokens"] = self.config.max_tokens

            if self.config.api_key:
                completion_params["api_key"] = self.config.api_key

            # Map reasoning parameters via provider-specific mapper
            if self.mapper.supports_reasoning(self.model_without_route):
                reasoning_params = self.mapper.map_reasoning_params(
                    self.config.enable_reasoning,
                    self.config.thinking_budget
                )
                completion_params.update(reasoning_params)

            response = self.litellm.completion(**completion_params)

            self._process_streaming_response(response, streaming_callback, final_callback)

        except self.litellm_exceptions.InternalServerError as e:
            pr_err(f"Dictation API error: Internal error encountered")
            pr_err(f"This is a transient error from the API provider")
            pr_err(f"Error details: {str(e)}")
            raise
        except Exception as e:
            operation = "audio transcription" if audio_data is not None else "text processing"
            self._handle_provider_error(e, operation)
    
    def get_xml_instructions(self) -> str:
        """Get the composed XML instructions from files."""
        # Determine audio source name for instruction loading
        audio_source_name = None
        if self.config.audio_source in ['transcribe', 'trans']:
            transcription_lower = self.config.transcription_model.lower()
            if 'wav2vec2' in transcription_lower or 'huggingface' in transcription_lower:
                audio_source_name = 'wav2vec2'
            elif 'vosk' in transcription_lower:
                audio_source_name = 'vosk'
            elif 'whisper' in transcription_lower:
                audio_source_name = 'whisper'

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
            pr_debug(f"Model processing time: {model_time:.3f}s")

    def _handle_provider_error(self, error: Exception, operation: str) -> None:
        """Common error handling for provider operations with full error details."""
        import traceback

        # Print full error details for debugging
        pr_err(f"ERROR during {operation}:")
        pr_err(f"Error Type: {type(error).__name__}")
        pr_err(f"Error Message: {str(error)}")

        if hasattr(self, 'google_exceptions'):
            # Gemini-specific errors
            if isinstance(error, self.google_exceptions.InvalidArgument):
                pr_err(f"Gemini API Error (Invalid Argument) - check your request parameters")
            elif isinstance(error, self.google_exceptions.PermissionDenied):
                pr_err(f"Gemini API Error (Permission Denied) - check your API key and permissions")
            elif isinstance(error, self.google_exceptions.ResourceExhausted):
                pr_err(f"Gemini API Error (Rate Limit/Quota) - you may have exceeded usage limits")
            else:
                pr_err(f"Gemini API Error - see details above")
        elif hasattr(self, 'GroqError'):
            # Groq-specific errors
            if isinstance(error, self.GroqError):
                pr_err(f"Groq API Error - see details above")
            else:
                pr_err(f"Groq Provider Error - see details above")
        else:
            pr_err(f"Provider Error - see details above")

        # Print stack trace for debugging
        pr_debug(f"Stack trace:")
        traceback.print_exc(file=sys.stderr)

    def _display_cache_stats(self, usage_data, completion_response=None) -> None:
        """Display cache statistics and cost from usage data."""
        if not self.config.debug_enabled:
            return

        pr_debug("-" * 60)
        pr_debug("USAGE STATISTICS:")

        # Standard token counts
        if hasattr(usage_data, 'prompt_tokens'):
            pr_debug(f"  Prompt tokens: {usage_data.prompt_tokens}")
        if hasattr(usage_data, 'completion_tokens'):
            pr_debug(f"  Completion tokens: {usage_data.completion_tokens}")
        if hasattr(usage_data, 'total_tokens'):
            pr_debug(f"  Total tokens: {usage_data.total_tokens}")

        # Anthropic-specific cache fields
        if hasattr(usage_data, 'cache_creation_input_tokens') and usage_data.cache_creation_input_tokens:
            pr_debug(f"  Cache creation tokens: {usage_data.cache_creation_input_tokens} (Anthropic: written to cache)")

        if hasattr(usage_data, 'cache_read_input_tokens') and usage_data.cache_read_input_tokens:
            pr_debug(f"  Cache read tokens: {usage_data.cache_read_input_tokens} (Anthropic: read from cache)")

        # DeepSeek-specific cache fields
        if hasattr(usage_data, 'prompt_cache_hit_tokens') and usage_data.prompt_cache_hit_tokens:
            pr_debug(f"  Cache hit tokens: {usage_data.prompt_cache_hit_tokens} (DeepSeek: cache hits)")

        if hasattr(usage_data, 'prompt_cache_miss_tokens') and usage_data.prompt_cache_miss_tokens:
            pr_debug(f"  Cache miss tokens: {usage_data.prompt_cache_miss_tokens} (DeepSeek: cache misses)")

        # OpenAI/Gemini format: prompt_tokens_details
        if hasattr(usage_data, 'prompt_tokens_details') and usage_data.prompt_tokens_details:
            details = usage_data.prompt_tokens_details

            # Show audio tokens if present
            if hasattr(details, 'audio_tokens') and details.audio_tokens:
                pr_debug(f"  Audio tokens: {details.audio_tokens}")

            # Show text tokens if present
            if hasattr(details, 'text_tokens') and details.text_tokens:
                pr_debug(f"  Text tokens: {details.text_tokens}")

            # Show cached tokens (None = no caching, 0 = cache warming, >0 = cache hit)
            if hasattr(details, 'cached_tokens'):
                if details.cached_tokens is None:
                    pr_debug(f"  Cached tokens: None (no implicit caching detected)")
                elif details.cached_tokens == 0:
                    pr_debug(f"  Cached tokens: 0 (cache warming - first request)")
                else:
                    pr_debug(f"  Cached tokens: {details.cached_tokens} (cache hit!)")

        # Completion token details
        if hasattr(usage_data, 'completion_tokens_details') and usage_data.completion_tokens_details:
            details = usage_data.completion_tokens_details

            # Show reasoning tokens if present (extended thinking)
            if hasattr(details, 'reasoning_tokens') and details.reasoning_tokens:
                pr_debug(f"  Reasoning tokens: {details.reasoning_tokens} (extended thinking)")

        # Gemini-specific: cached_content_token_count (alternative field)
        if hasattr(usage_data, 'cached_content_token_count') and usage_data.cached_content_token_count:
            pr_debug(f"  Cached content tokens: {usage_data.cached_content_token_count} (Gemini: implicit cache)")

        # Calculate and display cost
        if completion_response:
            try:
                current_cost = self.litellm.completion_cost(completion_response=completion_response)
                self.total_cost += current_cost
                pr_debug(f"COST:")
                pr_debug(f"  Current request: ${current_cost:.6f}")
                pr_debug(f"  Total session: ${self.total_cost:.6f}")
            except Exception as e:
                pr_debug(f"COST: Unable to calculate ({str(e)})")

        pr_debug("-" * 60)

    def _display_user_content(self, user_content):
        """Display user content being sent to model."""
        pr_debug("=" * 60)
        pr_debug("SENDING TO MODEL:")

        # Handle list format (audio transcription)
        if isinstance(user_content, list):
            for content_block in user_content:
                if content_block["type"] == "text":
                    pr_debug(content_block["text"])
                elif content_block["type"] == "input_audio":
                    pr_debug("Audio: audio_data.wav (base64)")
        # Handle string format (text transcription)
        else:
            pr_debug(user_content)

        pr_debug("-" * 60)

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
