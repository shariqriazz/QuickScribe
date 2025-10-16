"""Factory for creating transcription audio sources."""

from transcription.implementations.huggingface import HuggingFaceTranscriptionAudioSource
from transcription.implementations.openai import OpenAITranscriptionAudioSource
from transcription.implementations.vosk import VoskTranscriptionAudioSource


_TRANSCRIPTION_IMPLEMENTATIONS = {
    'huggingface': HuggingFaceTranscriptionAudioSource,
    'openai': OpenAITranscriptionAudioSource,
    'vosk': VoskTranscriptionAudioSource,
}


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

    provider = transcription_model.split('/', 1)[0].lower()
    implementation_class = _TRANSCRIPTION_IMPLEMENTATIONS.get(provider)

    if implementation_class is None:
        raise ValueError(
            f"Unsupported transcription provider: '{provider}'. "
            f"Supported providers: {', '.join(_TRANSCRIPTION_IMPLEMENTATIONS.keys())}"
        )

    return implementation_class(config, transcription_model)
