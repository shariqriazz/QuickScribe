"""HuggingFace transcription implementations for QuickScribe."""

from .processor_utils import (
    CTCVocabDecoder,
    ProcessorWrapper,
    load_processor_with_fallback
)
from .ctc.chunk_handler import CTCChunkHandler
from .ctc.audio_source import HuggingFaceCTCTranscriptionAudioSource
from .seq2seq import (
    HuggingFaceSeq2SeqTranscriptionAudioSource,
    WhisperTranscriptionAudioSource,
    Speech2TextTranscriptionAudioSource
)

__all__ = [
    'CTCVocabDecoder',
    'ProcessorWrapper',
    'load_processor_with_fallback',
    'CTCChunkHandler',
    'HuggingFaceCTCTranscriptionAudioSource',
    'HuggingFaceSeq2SeqTranscriptionAudioSource',
    'WhisperTranscriptionAudioSource',
    'Speech2TextTranscriptionAudioSource'
]
