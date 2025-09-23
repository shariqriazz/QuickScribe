import os
import sys
import tempfile
import soundfile as sf
from typing import Optional, Dict, Any
from .base_provider import BaseProvider


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
                
        except self.GroqError as e:
            print(f"\nGroq API Error: {e}", file=sys.stderr)
            return None
        except Exception as e:
            print(f"\nUnexpected error during Groq transcription: {e}", file=sys.stderr)
            return None
        finally:
            # Clean up temporary file
            if tmp_filename and os.path.exists(tmp_filename):
                try:
                    os.remove(tmp_filename)
                except OSError as e:
                    print(f"\nError deleting temp file {tmp_filename}: {e}", file=sys.stderr)
    
    def transcribe_audio_file(self, filename: str, conversation_xml: str = "", compiled_text: str = "") -> Optional[str]:
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
                
        except self.GroqError as e:
            print(f"\nGroq API Error: {e}", file=sys.stderr)
            return None
        except Exception as e:
            print(f"\nUnexpected error during Groq transcription: {e}", file=sys.stderr)
            return None
    
    def transcribe_audio_bytes(self, wav_bytes: bytes, conversation_xml: str = "", compiled_text: str = "", 
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
            result = self.transcribe_audio_file(tmp_filename, conversation_xml, compiled_text)
            
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
    
    def get_provider_specific_instructions(self) -> str:
        """Get provider-specific instructions for prompts."""
        return ""  # Currently blank, can be customized per provider