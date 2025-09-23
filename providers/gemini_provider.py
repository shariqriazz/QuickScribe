import io
import os
import sys
import soundfile as sf
from typing import Optional, Generator, Tuple
from .base_provider import BaseProvider


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
    
    def transcribe_audio(self, audio_np, sample_rate: int, prompt: str = "") -> Optional[str]:
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
            
            # Generate streaming content
            response = self.model.generate_content(
                contents=contents,
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
            result = self.transcribe_audio(audio_np, sample_rate, prompt)
            if result:
                yield result
    
    def transcribe_audio_file(self, filename: str, conversation_xml: str = "", compiled_text: str = "") -> Optional[str]:
        """Transcribe audio from file (not directly supported by Gemini, convert to bytes)."""
        try:
            with open(filename, 'rb') as f:
                audio_bytes = f.read()
            return self.transcribe_audio_bytes_sync(audio_bytes, conversation_xml, compiled_text)
        except Exception as e:
            print(f"\nError reading audio file: {e}", file=sys.stderr)
            return None
    
    def transcribe_audio_bytes(self, wav_bytes: bytes, conversation_xml: str = "", compiled_text: str = "", 
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
            
            # Use streaming
            try:
                response = self.model.generate_content(
                    contents=contents,
                    stream=True
                )

                accumulated_text = ""
                for chunk in response:
                    if chunk.candidates and chunk.candidates[0].content and chunk.candidates[0].content.parts:
                        chunk_text = "".join(part.text for part in chunk.candidates[0].content.parts if hasattr(part, 'text'))
                        if chunk_text:
                            if streaming_callback:
                                streaming_callback(chunk_text)
                            accumulated_text += chunk_text

                if final_callback:
                    final_callback(accumulated_text)

            except Exception as stream_error:
                print(f"Streaming failed, using standard response: {stream_error}")
                response = self.model.generate_content(contents=contents)

                # Check for safety ratings first
                if response.candidates and response.candidates[0].safety_ratings:
                    print("\nSafety Ratings:")
                    for rating in response.candidates[0].safety_ratings:
                        print(f"  {rating.category.name}: {rating.probability.name}")

                # Check response structure carefully
                text_to_output = None
                if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
                    text_to_output = "".join(part.text for part in response.candidates[0].content.parts if hasattr(part, 'text'))
                elif hasattr(response, 'text'):
                    text_to_output = response.text

                if final_callback:
                    final_callback(text_to_output)

        except self.google_exceptions.InvalidArgument as e:
            print(f"\nGemini API Error (Invalid Argument): {e}", file=sys.stderr)
        except self.google_exceptions.PermissionDenied as e:
            print(f"\nGemini API Error (Permission Denied): {e}", file=sys.stderr)
        except self.google_exceptions.ResourceExhausted as e:
            print(f"\nGemini API Error (Rate Limit/Quota): {e}", file=sys.stderr)
        except Exception as e:
            print(f"\nUnexpected error during Gemini transcription: {e}", file=sys.stderr)
    
    def transcribe_audio_bytes_sync(self, wav_bytes: bytes, conversation_xml: str = "", compiled_text: str = "") -> Optional[str]:
        """Synchronous version of transcribe_audio_bytes."""
        result = None
        
        def final_callback(text):
            nonlocal result
            result = text
        
        self.transcribe_audio_bytes(wav_bytes, conversation_xml, compiled_text, final_callback=final_callback)
        return result
    
    def get_provider_specific_instructions(self) -> str:
        """Get provider-specific instructions for prompts."""
        return ""  # Currently blank, can be customized per provider