import io
import os
import sys
import soundfile as sf
import numpy as np
from typing import Optional, Generator, Tuple
from .base_provider import BaseProvider
from .conversation_context import ConversationContext


class GeminiProvider(BaseProvider):
    """Gemini provider for speech transcription."""
    
    def __init__(self, model_id: str, language: Optional[str] = None):
        super().__init__(model_id, language)  # Note: Gemini ignores language parameter
        self.model = None
    
    def initialize(self) -> bool:
        """Initialize the Gemini client."""
        try:
            import google.generativeai as genai
            from google.api_core import exceptions as google_exceptions
            self.genai = genai
            self.google_exceptions = google_exceptions
        except ImportError:
            print("Error: google-generativeai library not found. Please install it: pip install google-generativeai", file=sys.stderr)
            return False
        
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            print("Error: GOOGLE_API_KEY not found in environment variables or .env file.", file=sys.stderr)
            return False
        
        try:
            self.genai.configure(api_key=api_key)
            self.model = self.genai.GenerativeModel(self.model_id)
            print("Gemini client initialized.")
            self._initialized = True
            return True
        except Exception as e:
            print(f"Error configuring or creating Gemini model instance ({self.model_id}): {e}", file=sys.stderr)
            return False
    
    def is_initialized(self) -> bool:
        """Check if provider is initialized."""
        return self._initialized and self.model is not None
    
    def _transcribe_audio_legacy(self, audio_np, sample_rate: int, prompt: str = "") -> Optional[str]:
        """Transcribe audio using Gemini API (non-streaming)."""
        if not self.is_initialized():
            print("\nError: Gemini model not initialized.", file=sys.stderr)
            return None
        
        try:
            # Convert audio to WAV bytes
            wav_bytes_io = io.BytesIO()
            sf.write(wav_bytes_io, audio_np, sample_rate, format='WAV', subtype='PCM_16')
            wav_bytes = wav_bytes_io.getvalue()
            wav_bytes_io.close()
            
            if len(wav_bytes) > 18 * 1024 * 1024:
                print("\nWarning: Audio data >18MB, may fail inline Gemini request.")
            
            # Prepare request
            full_prompt = f"Transcript with XML formatting: {prompt}" if prompt.strip() else "Transcribe this audio:"
            audio_blob = {"mime_type": "audio/wav", "data": wav_bytes}
            contents = [full_prompt, audio_blob]
            
            # Generate content
            response = self.model.generate_content(contents=contents)
            
            # Check for safety ratings
            if response.candidates and response.candidates[0].safety_ratings:
                print("\nSafety Ratings:")
                for rating in response.candidates[0].safety_ratings:
                    print(f"  {rating.category.name}: {rating.probability.name}")
            
            # Extract text from response
            text_to_output = None
            if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
                text_to_output = "".join(part.text for part in response.candidates[0].content.parts if hasattr(part, 'text'))
            elif hasattr(response, 'text'):
                text_to_output = response.text
            
            if not text_to_output:
                print("\nGemini did not return text.")
                if response.candidates and response.candidates[0].finish_reason:
                    print(f"Finish reason: {response.candidates[0].finish_reason.name}")
                return None
            
            return text_to_output
            
        except self.google_exceptions.InvalidArgument as e:
            print(f"\nGemini API Error (Invalid Argument): {e}", file=sys.stderr)
            return None
        except self.google_exceptions.PermissionDenied as e:
            print(f"\nGemini API Error (Permission Denied): {e}", file=sys.stderr)
            return None
        except self.google_exceptions.ResourceExhausted as e:
            print(f"\nGemini API Error (Rate Limit/Quota): {e}", file=sys.stderr)
            return None
        except Exception as e:
            print(f"\nUnexpected error during Gemini transcription: {e}", file=sys.stderr)
            return None
    
    def transcribe_audio_streaming(self, audio_np, sample_rate: int, prompt: str = "") -> Generator[str, None, None]:
        """Transcribe audio using Gemini API with streaming."""
        if not self.is_initialized():
            print("\nError: Gemini model not initialized.", file=sys.stderr)
            return
        
        try:
            # Convert audio to WAV bytes
            wav_bytes_io = io.BytesIO()
            sf.write(wav_bytes_io, audio_np, sample_rate, format='WAV', subtype='PCM_16')
            wav_bytes = wav_bytes_io.getvalue()
            wav_bytes_io.close()
            
            if len(wav_bytes) > 18 * 1024 * 1024:
                print("\nWarning: Audio data >18MB, may fail inline Gemini request.")
            
            # Prepare request
            full_prompt = f"Transcript with XML formatting: {prompt}" if prompt.strip() else "Transcribe this audio:"
            audio_blob = {"mime_type": "audio/wav", "data": wav_bytes}
            contents = [full_prompt, audio_blob]
            
            # Generate streaming content with 2025 optimized config
            generation_config = {
                'temperature': self.temperature,
                'top_p': self.top_p,
                'top_k': 40,  # Recommended for speed optimization
                'candidate_count': 1  # Single response for maximum speed
            }

            response = self.model.generate_content(
                contents=contents,
                generation_config=generation_config,
                stream=True
            )
            
            for chunk in response:
                if chunk.candidates and chunk.candidates[0].content and chunk.candidates[0].content.parts:
                    chunk_text = "".join(part.text for part in chunk.candidates[0].content.parts if hasattr(part, 'text'))
                    if chunk_text:
                        yield chunk_text
                        
        except Exception as e:
            print(f"Streaming failed: {e}")
            # Fallback to non-streaming
            result = self._transcribe_audio_legacy(audio_np, sample_rate, prompt)
            if result:
                yield result
    
    def transcribe_audio(self, audio_np: np.ndarray, context: ConversationContext,
                        streaming_callback=None, final_callback=None) -> None:
        """Unified transcription interface with internal bytes handling."""
        if not self.is_initialized():
            print("\nError: Gemini model not initialized.", file=sys.stderr)
            return

        try:
            # Convert audio to WAV bytes
            wav_bytes_io = io.BytesIO()
            sf.write(wav_bytes_io, audio_np, context.sample_rate, format='WAV', subtype='PCM_16')
            wav_bytes = wav_bytes_io.getvalue()
            wav_bytes_io.close()

            if len(wav_bytes) > 18 * 1024 * 1024:
                print("\nWarning: Audio data >18MB, may fail inline Gemini request.")

            # Get conversation context
            conversation_xml = context.xml_markup
            compiled_text = context.compiled_text
            
            # Display conversation flow
            self._display_conversation_context(context, "[audio_data.wav]")
            
            print("\nRECEIVED FROM MODEL (streaming):")
            self._transcribe_audio_bytes(wav_bytes, conversation_xml, compiled_text, 
                                       streaming_callback, final_callback)
                
        except Exception as e:
            print(f"\nError during Gemini transcription: {e}", file=sys.stderr)

    def _transcribe_audio_file(self, filename: str, conversation_xml: str = "", compiled_text: str = "") -> Optional[str]:
        """Transcribe audio from file (not directly supported by Gemini, convert to bytes)."""
        try:
            with open(filename, 'rb') as f:
                audio_bytes = f.read()
            return self._transcribe_audio_bytes_sync(audio_bytes, conversation_xml, compiled_text)
        except Exception as e:
            print(f"\nError reading audio file: {e}", file=sys.stderr)
            return None
    
    def _transcribe_audio_bytes(self, wav_bytes: bytes, conversation_xml: str = "", compiled_text: str = "", 
                               streaming_callback=None, final_callback=None):
        """Transcribe audio from bytes with streaming support."""
        if not self.is_initialized():
            print("\nError: Gemini model not initialized.", file=sys.stderr)
            return

        try:
            xml_instructions = self.get_xml_instructions()
            
            prompt = f"Transcript with XML formatting: {xml_instructions}"
            if conversation_xml:
                prompt += f" Current conversation XML: {conversation_xml}\nCurrent conversation text: {compiled_text}"
            
            audio_blob = {"mime_type": "audio/wav", "data": wav_bytes}
            contents = [prompt, audio_blob]

            # Use streaming with 2025 optimized generation config
            generation_config = {
                'temperature': self.temperature,
                'top_p': self.top_p,
                'top_k': 40,  # Recommended for speed optimization
                'candidate_count': 1  # Single response for maximum speed
            }

            try:
                response = self.model.generate_content(
                    contents=contents,
                    generation_config=generation_config,
                    stream=True
                )
            except StopIteration:
                print("\n⚠️  Gemini API returned empty stream immediately (StopIteration on first access)", file=sys.stderr)
                print("This indicates the API rejected the request before generating any response", file=sys.stderr)
                if final_callback:
                    final_callback("")
                return
            except Exception as gen_error:
                print(f"\n❌ Error calling generate_content: {gen_error}", file=sys.stderr)
                raise

            accumulated_text = ""
            chunk_count = 0
            for chunk in response:
                chunk_count += 1

                if chunk.prompt_feedback:
                    print(f"\n⚠️  Gemini prompt feedback: {chunk.prompt_feedback}", file=sys.stderr)
                    if hasattr(chunk.prompt_feedback, 'block_reason'):
                        print(f"Block reason: {chunk.prompt_feedback.block_reason}", file=sys.stderr)

                if chunk.candidates:
                    candidate = chunk.candidates[0]

                    if hasattr(candidate, 'finish_reason') and candidate.finish_reason:
                        finish_reason_value = candidate.finish_reason
                        if finish_reason_value not in [1, 'STOP']:
                            print(f"\n⚠️  Gemini finish reason: {finish_reason_value}", file=sys.stderr)

                    if hasattr(candidate, 'safety_ratings') and candidate.safety_ratings:
                        for rating in candidate.safety_ratings:
                            if hasattr(rating, 'blocked') and rating.blocked:
                                print(f"\n🚫 Content blocked by safety filter: {rating.category} - {rating.probability}", file=sys.stderr)

                    if candidate.content and candidate.content.parts:
                        chunk_text = "".join(part.text for part in candidate.content.parts if hasattr(part, 'text'))
                        if chunk_text:
                            self.mark_first_response()
                            if streaming_callback:
                                streaming_callback(chunk_text)
                            accumulated_text += chunk_text

            if chunk_count == 0:
                print("\nWarning: Gemini returned empty response (StopIteration) - audio may be too short or invalid", file=sys.stderr)

            if final_callback:
                final_callback(accumulated_text)

        except Exception as e:
            self._handle_provider_error(e, "Gemini transcription")
    
    def _transcribe_audio_bytes_sync(self, wav_bytes: bytes, conversation_xml: str = "", compiled_text: str = "") -> Optional[str]:
        """Synchronous version of transcribe_audio_bytes."""
        result = None
        
        def final_callback(text):
            nonlocal result
            result = text
        
        self._transcribe_audio_bytes(wav_bytes, conversation_xml, compiled_text, final_callback=final_callback)
        return result
    
    def transcribe_text(self, text: str, context: ConversationContext,
                       streaming_callback=None, final_callback=None) -> None:
        """Process pre-transcribed text through Gemini chat API."""
        if not self.is_initialized():
            print("\nError: Gemini model not initialized.", file=sys.stderr)
            return

        try:
            # Get conversation context
            conversation_xml = context.xml_markup
            compiled_text = context.compiled_text

            # Display conversation flow
            self._display_text_context(context, text)

            # Process with Gemini chat API
            result = self._transcribe_text_chat(text, conversation_xml, compiled_text, streaming_callback)
            if result and final_callback:
                final_callback(result)

        except Exception as e:
            print(f"\nError during Gemini text transcription: {e}", file=sys.stderr)

    def _transcribe_text_chat(self, text: str, conversation_xml: str = "", compiled_text: str = "",
                             streaming_callback=None) -> Optional[str]:
        """Process text using Gemini chat completion API."""
        if not self.is_initialized():
            print("\nError: Gemini model not initialized.", file=sys.stderr)
            return None

        try:
            xml_instructions = self.get_xml_instructions()

            # Build prompt for text processing
            prompt = f"Transcript with XML formatting: {xml_instructions}"

            prompt += f"\n\nCURRENT STATE (already processed):"
            prompt += f"\nXML markup: {conversation_xml if conversation_xml else '[empty]'}"
            prompt += f"\nRendered text: {compiled_text if compiled_text else '[empty]'}"

            prompt += f"\n\nNEW INPUT (requires processing):"
            prompt += f"\nMechanical transcription: {text}"

            prompt += "\n\nCRITICAL: The 'mechanical transcription' above is raw output from automatic speech recognition (VOSK). It requires the SAME analysis as audio input:"
            prompt += "\n- Treat as if you just heard the audio yourself"
            prompt += "\n- Identify sound-alike errors: \"there/their\", \"to/too\", \"no/know\", etc."
            prompt += "\n- Fix misrecognized words based on context"
            prompt += "\n- Apply ALL copy editing and formatting rules"
            prompt += "\n- Handle false starts, fillers, and speech patterns"
            prompt += "\n- Generate TX (literal with sound-alike options), INT (clean edited), UPDATE (XML tags)"

            # Use streaming with 2025 optimized generation config
            generation_config = {
                'temperature': self.temperature,
                'top_p': self.top_p,
                'top_k': 40,  # Recommended for speed optimization
                'candidate_count': 1  # Single response for maximum speed
            }

            response = self.model.generate_content(
                contents=[prompt],
                generation_config=generation_config,
                stream=True
            )

            print("\nRECEIVED FROM MODEL (streaming):")
            accumulated_text = ""
            for chunk in response:
                if chunk.candidates and chunk.candidates[0].content and chunk.candidates[0].content.parts:
                    chunk_text = "".join(part.text for part in chunk.candidates[0].content.parts if hasattr(part, 'text'))
                    if chunk_text:
                        # Mark first response timing
                        self.mark_first_response()
                        if streaming_callback:
                            streaming_callback(chunk_text)
                        accumulated_text += chunk_text

            return accumulated_text

        except Exception as e:
            self._handle_provider_error(e, "Gemini text processing")
            return None

