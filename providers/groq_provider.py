import os
import sys
import tempfile
import soundfile as sf
import numpy as np
from typing import Optional, Dict, Any
from .base_provider import BaseProvider
from .conversation_context import ConversationContext


class GroqProvider(BaseProvider):
    """Groq provider for speech transcription."""
    
    def __init__(self, model_id: str, language: Optional[str] = None):
        super().__init__(model_id, language)
        self.client = None
    
    def initialize(self) -> bool:
        """Initialize the Groq client."""
        try:
            from groq import Groq, GroqError
            self.GroqError = GroqError
        except ImportError:
            print("Error: groq library not found. Please install it: pip install groq", file=sys.stderr)
            return False
        
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            print("Error: GROQ_API_KEY not found in environment variables or .env file.", file=sys.stderr)
            return False
        
        try:
            self.client = Groq(api_key=api_key)
            print("Groq client initialized.")
            self._initialized = True
            return True
        except Exception as e:
            print(f"Error initializing Groq client: {e}", file=sys.stderr)
            return False
    
    def is_initialized(self) -> bool:
        """Check if provider is initialized."""
        return self._initialized and self.client is not None
    
    def transcribe_audio(self, audio_np, sample_rate: int, prompt: str = "") -> Optional[str]:
        """Transcribe audio using Groq API."""
        if not self.is_initialized():
            print("\nError: Groq client not initialized.", file=sys.stderr)
            return None
        
        tmp_filename = None
        try:
            # Save audio to temporary file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
                tmp_filename = tmp_file.name
                sf.write(tmp_filename, audio_np, sample_rate)
            
            # Prepare transcription parameters
            with open(tmp_filename, "rb") as file_for_groq:
                transcription_params = {
                    "file": (os.path.basename(tmp_filename), file_for_groq.read()),
                    "model": self.model_id,
                    "language": self.language
                }
                
                # Add prompt if provided
                if prompt.strip():
                    transcription_params["prompt"] = prompt
                
                # Create transcription
                transcription = self.client.audio.transcriptions.create(**transcription_params)
                return transcription.text

        except Exception as e:
            self._handle_provider_error(e, "Groq transcription")
            return None
        finally:
            # Clean up temporary file
            if tmp_filename and os.path.exists(tmp_filename):
                try:
                    os.remove(tmp_filename)
                except OSError as e:
                    print(f"\nError deleting temp file {tmp_filename}: {e}", file=sys.stderr)
    
    def transcribe_audio(self, audio_np: np.ndarray, context: ConversationContext,
                        streaming_callback=None, final_callback=None) -> None:
        """Unified transcription interface with internal file handling."""
        if not self.is_initialized():
            print("\nError: Groq client not initialized.", file=sys.stderr)
            return
        
        tmp_filename = None
        try:
            # Save audio to temporary file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
                tmp_filename = tmp_file.name
                sf.write(tmp_filename, audio_np, context.sample_rate)
            
            # Get conversation context
            conversation_xml = context.xml_markup
            compiled_text = context.compiled_text
            
            # Display conversation flow
            self._display_conversation_context(context, os.path.basename(tmp_filename))
            
            # Transcribe with provider
            result = self._transcribe_audio_file(tmp_filename, conversation_xml, compiled_text)
            if result and final_callback:
                final_callback(result)
                
        except Exception as e:
            print(f"\nError during Groq transcription: {e}", file=sys.stderr)
        finally:
            # Clean up temporary file
            if tmp_filename and os.path.exists(tmp_filename):
                try:
                    os.remove(tmp_filename)
                except OSError as e:
                    print(f"\nError deleting temp file {tmp_filename}: {e}", file=sys.stderr)

    def _transcribe_audio_file(self, filename: str, conversation_xml: str = "", compiled_text: str = "") -> Optional[str]:
        """Transcribe audio from file using Groq API."""
        if not self.is_initialized():
            print("\nError: Groq client not initialized.", file=sys.stderr)
            return None

        try:
            xml_instructions = self.get_xml_instructions()
            
            prompt = xml_instructions
            if conversation_xml:
                prompt += f" Current conversation XML: {conversation_xml}\nCurrent conversation text: {compiled_text}"
            
            with open(filename, "rb") as audio_file:
                transcription_params = {
                    "file": (os.path.basename(filename), audio_file.read()),
                    "model": self.model_id,
                    "prompt": prompt
                }
                
                if self.language:
                    transcription_params["language"] = self.language
                
                transcription = self.client.audio.transcriptions.create(**transcription_params)
                return transcription.text

        except Exception as e:
            self._handle_provider_error(e, "Groq transcription")
            return None
    
    def _transcribe_audio_bytes(self, wav_bytes: bytes, conversation_xml: str = "", compiled_text: str = "", 
                               streaming_callback=None, final_callback=None):
        """Transcribe audio from bytes (Groq doesn't support bytes directly, save to temp file)."""
        if not self.is_initialized():
            print("\nError: Groq client not initialized.", file=sys.stderr)
            return
        
        tmp_filename = None
        try:
            # Save bytes to temporary file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
                tmp_filename = tmp_file.name
                tmp_file.write(wav_bytes)
            
            # Use file transcription
            result = self._transcribe_audio_file(tmp_filename, conversation_xml, compiled_text)
            
            if final_callback:
                final_callback(result)
                
        except Exception as e:
            print(f"\nError in transcribe_audio_bytes: {e}", file=sys.stderr)
        finally:
            if tmp_filename and os.path.exists(tmp_filename):
                try:
                    os.remove(tmp_filename)
                except OSError as e:
                    print(f"\nError deleting temp file {tmp_filename}: {e}", file=sys.stderr)
    
    def transcribe_text(self, text: str, context: ConversationContext,
                       streaming_callback=None, final_callback=None) -> None:
        """Process pre-transcribed text through Groq chat API."""
        if not self.is_initialized():
            print("\nError: Groq client not initialized.", file=sys.stderr)
            return

        try:
            # Get conversation context
            conversation_xml = context.xml_markup
            compiled_text = context.compiled_text

            # Display conversation flow
            self._display_text_context(context, text)

            # Process with Groq chat API
            result = self._transcribe_text_chat(text, conversation_xml, compiled_text, streaming_callback)
            if result and final_callback:
                final_callback(result)

        except Exception as e:
            print(f"\nError during Groq text transcription: {e}", file=sys.stderr)

    def _transcribe_text_chat(self, text: str, conversation_xml: str = "", compiled_text: str = "",
                             streaming_callback=None) -> Optional[str]:
        """Process text using Groq chat completion API."""
        if not self.is_initialized():
            print("\nError: Groq client not initialized.", file=sys.stderr)
            return None

        try:
            xml_instructions = self.get_xml_instructions()

            # Build prompt for text processing
            prompt = xml_instructions

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

            # Use chat completion
            messages = [
                {"role": "system", "content": "You are an intelligent transcription assistant."},
                {"role": "user", "content": prompt}
            ]

            # Build completion parameters
            completion_params = {
                "model": self.model_id,
                "messages": messages,
                "temperature": self.temperature,
                "top_p": self.top_p,
                "stream": True
            }

            # Only include max_tokens if specified
            if self.max_tokens is not None:
                completion_params["max_tokens"] = self.max_tokens

            completion = self.client.chat.completions.create(**completion_params)

            print("\nRECEIVED FROM MODEL (streaming):")
            accumulated_text = ""
            for chunk in completion:
                if chunk.choices[0].delta.content is not None:
                    chunk_text = chunk.choices[0].delta.content
                    if streaming_callback:
                        streaming_callback(chunk_text)
                    accumulated_text += chunk_text

            return accumulated_text

        except Exception as e:
            self._handle_provider_error(e, "Groq text processing")
            return None

