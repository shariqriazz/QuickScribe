"""HuggingFace transcription implementations for QuickScribe."""

from .processor_utils import (
    SimpleTokenizerWrapper,
    ProcessorWrapper,
    load_processor_with_fallback,
    is_phoneme_tokenizer,
    format_ctc_output
)
from .ctc.chunk_handler import CTCChunkHandler
from .ctc.audio_source import HuggingFaceCTCTranscriptionAudioSource
from .seq2seq.audio_source import HuggingFaceSeq2SeqTranscriptionAudioSource

__all__ = [
    'SimpleTokenizerWrapper',
    'ProcessorWrapper',
    'load_processor_with_fallback',
    'is_phoneme_tokenizer',
    'format_ctc_output',
    'CTCChunkHandler',
    'HuggingFaceCTCTranscriptionAudioSource',
    'HuggingFaceSeq2SeqTranscriptionAudioSource'
]
