"""OpenAI Whisper transcription implementation for QuickScribe."""

import sys
import base64
import numpy as np
import io
from typing import Optional

try:
    import litellm
    import soundfile as sf
except ImportError:
    litellm = None
    sf = None

from transcription.base import TranscriptionAudioSource


class OpenAITranscriptionAudioSource(TranscriptionAudioSource):
    """OpenAI Whisper transcription implementation using litellm."""

    def __init__(self, config, model_identifier: str, api_key: Optional[str] = None, dtype: str = 'int16'):
        super().__init__(config, model_identifier, supports_streaming=False, dtype=dtype)

        self.api_key = api_key

        if litellm is None:
            raise ImportError("litellm library not installed. Install with: pip install litellm")
        if sf is None:
            raise ImportError("soundfile library not installed. Install with: pip install soundfile")

    def _transcribe_audio(self, audio_data: np.ndarray) -> str:
        """Transcribe audio using OpenAI Whisper API."""
        try:
            if len(audio_data) == 0:
                return ""

            audio_data = self.normalize_to_float32(audio_data)
            audio_data = self.squeeze_to_mono(audio_data)

            if not self.validate_audio_length(audio_data, self.config.sample_rate):
                print("Audio too short for Whisper", file=sys.stderr)
                return ""

            audio_bytes = io.BytesIO()
            sf.write(audio_bytes, audio_data, self.config.sample_rate, format='WAV')
            audio_bytes.seek(0)
            audio_bytes.name = "audio.wav"

            transcription_params = {
                "model": self.model_identifier,
                "file": audio_bytes,
            }

            if self.api_key:
                transcription_params["api_key"] = self.api_key

            response = litellm.transcription(**transcription_params)

            transcribed_text = response.get('text', '').strip()
            return transcribed_text

        except Exception as e:
            print(f"Error transcribing with Whisper: {e}", file=sys.stderr)
            return ""

    def initialize(self) -> bool:
        """Initialize OpenAI Whisper transcription source."""
        try:
            if litellm is None or sf is None:
                print("Error: litellm or soundfile library not available", file=sys.stderr)
                return False

            if not super().initialize():
                return False

            print(f"OpenAI Whisper initialized with model: {self.model_identifier}")
            return True

        except Exception as e:
            print(f"Error initializing Whisper: {e}", file=sys.stderr)
            return False
