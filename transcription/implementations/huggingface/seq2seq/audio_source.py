"""HuggingFace Seq2Seq transcription implementation for QuickScribe."""

import sys
import numpy as np

sys.path.insert(0, 'lib')
from pr_log import pr_err, pr_warn, pr_info

try:
    import torch
except ImportError:
    torch = None

from transcription.base import TranscriptionAudioSource


class HuggingFaceSeq2SeqTranscriptionAudioSource(TranscriptionAudioSource):
    """
    HuggingFace Seq2Seq transcription implementation.

    Supports encoder-decoder models like Whisper, Speech2Text, etc.
    Uses autoregressive generation for transcription.
    """

    def __init__(self, config, model, processor):
        """
        Initialize Seq2Seq transcription audio source.

        Args:
            config: Configuration object
            model: Pre-loaded AutoModelForSpeechSeq2Seq instance
            processor: Pre-loaded AutoProcessor instance
        """
        model_identifier = model.name_or_path if hasattr(model, 'name_or_path') else str(model)
        super().__init__(config, model_identifier, supports_streaming=False, dtype='float32')

        if torch is None:
            raise ImportError("PyTorch library not installed")

        self.model = model
        self.processor = processor
        self.device = model.device
        self.torch_dtype = model.dtype

        pr_info(f"Initialized Seq2Seq model on device: {self.device}")

    def _transcribe_audio(self, audio_data: np.ndarray) -> str:
        """
        Transcribe audio using Seq2Seq model.

        Args:
            audio_data: Audio data array

        Returns:
            Transcribed text
        """
        try:
            audio_data = self.normalize_to_float32(audio_data)
            audio_data = self.squeeze_to_mono(audio_data)

            if not self.validate_audio_length(audio_data, self.config.sample_rate):
                pr_warn("Audio too short for Seq2Seq transcription")
                return ""

            inputs = self.processor(
                audio_data,
                sampling_rate=self.config.sample_rate,
                return_tensors="pt",
                return_attention_mask=True
            )

            input_features = inputs.input_features.to(self.device, dtype=self.torch_dtype)

            generate_kwargs = {
                "input_features": input_features,
                "task": "transcribe"
            }

            if hasattr(inputs, 'attention_mask') and inputs.attention_mask is not None:
                generate_kwargs["attention_mask"] = inputs.attention_mask.to(self.device)

            if hasattr(self.config, 'transcription_lang') and self.config.transcription_lang:
                lang_token = f"<|{self.config.transcription_lang}|>"
                generate_kwargs["language"] = lang_token
                pr_info(f"Using language: {self.config.transcription_lang}")

            with torch.no_grad():
                predicted_ids = self.model.generate(**generate_kwargs)

            transcription = self.processor.batch_decode(predicted_ids, skip_special_tokens=True)[0]

            return transcription.strip()

        except Exception as e:
            pr_err(f"Error during Seq2Seq transcription: {e}")
            return ""

    def initialize(self) -> bool:
        """Initialize Seq2Seq transcription source."""
        try:
            if torch is None:
                pr_err("PyTorch library not available")
                return False

            if not super().initialize():
                return False

            pr_info(f"Seq2Seq model initialized: {self.model_identifier}")
            return True

        except Exception as e:
            pr_err(f"Error initializing Seq2Seq model: {e}")
            return False
