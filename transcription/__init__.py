"""Transcription model implementations for QuickScribe."""

from .base import TranscriptionAudioSource
from .factory import get_transcription_source

__all__ = ['TranscriptionAudioSource', 'get_transcription_source']
