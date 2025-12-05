"""Whisper-specific transcription implementation."""

import sys
import numpy as np

sys.path.insert(0, 'lib')
from pr_log import pr_info

from .base import HuggingFaceSeq2SeqTranscriptionAudioSource


class WhisperTranscriptionAudioSource(HuggingFaceSeq2SeqTranscriptionAudioSource):
    """Whisper-specific transcription implementation."""

    def _prepare_generate_kwargs(self, inputs):
        """
        Prepare generation kwargs for Whisper models.

        Whisper models accept task and language parameters.

        Args:
            inputs: Processor output with input_features

        Returns:
            Dict of generation kwargs
        """
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

        return generate_kwargs
