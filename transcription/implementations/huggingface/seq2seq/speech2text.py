"""Speech2Text-specific transcription implementation."""

from .base import HuggingFaceSeq2SeqTranscriptionAudioSource


class Speech2TextTranscriptionAudioSource(HuggingFaceSeq2SeqTranscriptionAudioSource):
    """Speech2Text-specific transcription implementation."""

    def _prepare_generate_kwargs(self, inputs):
        """
        Prepare generation kwargs for Speech2Text models.

        Speech2Text models do not accept task/language parameters.

        Args:
            inputs: Processor output with input_features

        Returns:
            Dict of generation kwargs
        """
        input_features = inputs.input_features.to(self.device, dtype=self.torch_dtype)

        generate_kwargs = {"input_features": input_features}

        if hasattr(inputs, 'attention_mask') and inputs.attention_mask is not None:
            generate_kwargs["attention_mask"] = inputs.attention_mask.to(self.device)

        return generate_kwargs
