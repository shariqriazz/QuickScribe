"""
Audio source abstractions for QuickScribe.
"""
import numpy as np
from abc import ABC, abstractmethod
from types import TracebackType
from typing import Optional, Type, Protocol


class AudioResult:
    """Base class for audio results with discrimination."""

    def __init__(self, result_type: str, sample_rate: int):
        self.result_type = result_type
        self.sample_rate = sample_rate


class AudioDataResult(AudioResult):
    """Result containing raw audio data."""

    def __init__(self, audio_data: np.ndarray, sample_rate: int):
        super().__init__("audio_data", sample_rate)
        self.audio_data = audio_data


class AudioFileResult(AudioResult):
    """Result containing path to audio file."""

    def __init__(self, file_path: str, sample_rate: int):
        super().__init__("audio_file", sample_rate)
        self.file_path = file_path


class AudioTextResult(AudioResult):
    """Result containing transcribed text."""

    def __init__(self, transcribed_text: str, sample_rate: int, audio_data: Optional[np.ndarray] = None):
        super().__init__("audio_text", sample_rate)
        self.transcribed_text = transcribed_text
        self.audio_data = audio_data


class AudioChunkHandler(Protocol):
    """Protocol for handling streaming audio chunks."""

    def on_chunk(self, chunk: np.ndarray, timestamp: float) -> None:
        """
        Called for each audio chunk during recording.

        Args:
            chunk: Audio data for this chunk
            timestamp: Timestamp when chunk was captured
        """
        pass


class DefaultAudioChunkHandler:
    """Default handler that does nothing (maintains current behavior)."""

    def on_chunk(self, chunk: np.ndarray, timestamp: float) -> None:
        """No-op chunk handler."""
        pass


class AudioSource(ABC):
    """
    Abstract base class for audio sources.

    Implementations support context manager protocol for automatic cleanup.
    """

    def __init__(self, config):
        """Initialize with configuration."""
        self.config = config
        self._initialized = False

    @abstractmethod
    def initialize(self) -> bool:
        """
        Initialize the audio source.

        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    def start_recording(self) -> None:
        """Begin audio capture."""
        pass

    @abstractmethod
    def stop_recording(self) -> AudioResult:
        """
        Stop audio capture and return result.

        Returns:
            AudioResult containing captured audio
        """
        pass

    @abstractmethod
    def is_recording(self) -> bool:
        """Check if currently recording."""
        pass

    @abstractmethod
    def _cleanup(self) -> None:
        """Internal cleanup implementation."""
        pass


    # Context manager protocol for automatic cleanup
    def __enter__(self) -> 'AudioSource':
        """Enter context manager."""
        if not self._initialized:
            if not self.initialize():
                raise RuntimeError("Failed to initialize audio source")
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType]
    ) -> None:
        """Exit context manager and cleanup."""
        self._cleanup()