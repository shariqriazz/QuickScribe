"""HuggingFace Seq2Seq transcription implementations for QuickScribe."""

from .base import HuggingFaceSeq2SeqTranscriptionAudioSource
from .whisper import WhisperTranscriptionAudioSource
from .speech2text import Speech2TextTranscriptionAudioSource

__all__ = [
    'HuggingFaceSeq2SeqTranscriptionAudioSource',
    'WhisperTranscriptionAudioSource',
    'Speech2TextTranscriptionAudioSource'
]
