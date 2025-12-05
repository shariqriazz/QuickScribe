"""Factory for creating transcription audio sources."""

from transcription.base import parse_transcription_model
from transcription.implementations.huggingface.ctc import HuggingFaceCTCTranscriptionAudioSource
from transcription.implementations.huggingface.seq2seq import (
    WhisperTranscriptionAudioSource,
    Speech2TextTranscriptionAudioSource
)
from transcription.implementations.openai import OpenAITranscriptionAudioSource
from transcription.implementations.vosk import VoskTranscriptionAudioSource


_TRANSCRIPTION_IMPLEMENTATIONS = {
    'openai': OpenAITranscriptionAudioSource,
    'vosk': VoskTranscriptionAudioSource,
}

_HUGGINGFACE_IMPLEMENTATIONS = {
    'ctc': HuggingFaceCTCTranscriptionAudioSource,
    'whisper': WhisperTranscriptionAudioSource,
    'speech2text': Speech2TextTranscriptionAudioSource,
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

    if provider == 'huggingface':
        from transcription.implementations.huggingface.model_loader import load_huggingface_model

        model_identifier = parse_transcription_model(transcription_model)
        model, processor, architecture = load_huggingface_model(
            model_identifier,
            cache_dir=None,
            force_download=False,
            local_files_only=False
        )

        implementation_class = _HUGGINGFACE_IMPLEMENTATIONS.get(architecture)
        if implementation_class is None:
            raise ValueError(
                f"Unsupported HuggingFace architecture: '{architecture}'. "
                f"Supported architectures: {', '.join(_HUGGINGFACE_IMPLEMENTATIONS.keys())}"
            )

        return implementation_class(config, model, processor)

    else:
        implementation_class = _TRANSCRIPTION_IMPLEMENTATIONS.get(provider)
        if implementation_class is None:
            raise ValueError(
                f"Unsupported transcription provider: '{provider}'. "
                f"Supported providers: {', '.join(list(_TRANSCRIPTION_IMPLEMENTATIONS.keys()) + ['huggingface'])}"
            )

        return implementation_class(config, transcription_model)
