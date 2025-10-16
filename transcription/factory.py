"""Factory for creating transcription audio sources."""

import sys
from typing import Optional


def get_transcription_source(config):
    """
    Create transcription audio source based on model specification.

    Args:
        config: Configuration object with transcription_model attribute

    Returns:
        TranscriptionAudioSource instance

    Raises:
        ValueError: If provider not supported or model format invalid
    """
    transcription_model = config.transcription_model

    if '/' not in transcription_model:
        raise ValueError(
            f"Invalid transcription model format: '{transcription_model}'. "
            "Expected format: provider/model-identifier"
        )

    parts = transcription_model.split('/', 1)
    provider = parts[0].lower()
    model_identifier = parts[1]

    if provider == 'huggingface':
        from transcription.implementations.huggingface import HuggingFaceTranscriptionAudioSource
        return HuggingFaceTranscriptionAudioSource(
            config,
            transcription_model,
            dtype='float32'
        )

    elif provider == 'openai':
        from transcription.implementations.openai import OpenAITranscriptionAudioSource
        return OpenAITranscriptionAudioSource(
            config,
            transcription_model,
            api_key=config.api_key,
            dtype='int16'
        )

    elif provider == 'vosk':
        from transcription.implementations.vosk import VoskTranscriptionAudioSource

        return VoskTranscriptionAudioSource(
            config,
            transcription_model,
            lgraph_path=getattr(config, 'vosk_lgraph_path', None),
            dtype='int16'
        )

    else:
        raise ValueError(
            f"Unsupported transcription provider: '{provider}'. "
            "Supported providers: huggingface, openai, vosk"
        )
