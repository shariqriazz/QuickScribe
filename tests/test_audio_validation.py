"""Tests for audio recording validation in ProcessingCoordinator."""

import time
import numpy as np
from unittest.mock import Mock, MagicMock
from processing_coordinator import ProcessingCoordinator
from recording_session import RecordingSession, RecordingSource
from audio_source import AudioDataResult
from providers.conversation_context import ConversationContext


class MockConfig:
    """Mock configuration for testing."""

    def __init__(self):
        self.min_recording_duration = 1.0
        self.audio_amplitude_threshold = 0.05
        self.min_peak_duration = 0.5
        self.min_peak_duration_amplitude_threshold = 0.02
        self.sample_rate = 16000


class MockApp:
    """Mock application for testing."""

    def _return_to_idle(self):
        pass

    def _update_tray_state(self, state):
        pass

    def _show_recording_prompt(self):
        pass


def create_audio_result(audio_data, sample_rate=16000):
    """Create AudioDataResult for testing."""
    return AudioDataResult(audio_data=audio_data, sample_rate=sample_rate)


def create_session(start_time_offset=0.0):
    """Create RecordingSession with adjustable start time."""
    session = RecordingSession(RecordingSource.KEYBOARD)
    session.start_time = time.time() - start_time_offset
    return session


def test_validation_passes_with_valid_recording():
    """Valid recording with sufficient duration, amplitude, and peak duration passes."""
    config = MockConfig()
    app = MockApp()
    coordinator = ProcessingCoordinator(None, None, config, app)

    session = create_session(start_time_offset=1.5)

    sample_rate = 16000
    duration = 1.0
    samples = int(sample_rate * duration)
    audio_data = np.full(samples, 3000, dtype=np.int16)

    result = create_audio_result(audio_data, sample_rate)
    assert coordinator._validate_audio_recording(session, result) is True


def test_validation_rejects_too_short_duration():
    """Recording shorter than minimum duration is rejected."""
    config = MockConfig()
    app = MockApp()
    coordinator = ProcessingCoordinator(None, None, config, app)

    session = create_session(start_time_offset=0.5)

    sample_rate = 16000
    duration = 0.5
    samples = int(sample_rate * duration)
    audio_data = np.full(samples, 3000, dtype=np.int16)

    result = create_audio_result(audio_data, sample_rate)
    assert coordinator._validate_audio_recording(session, result) is False


def test_validation_rejects_low_amplitude():
    """Recording with amplitude below threshold is rejected."""
    config = MockConfig()
    app = MockApp()
    coordinator = ProcessingCoordinator(None, None, config, app)

    session = create_session(start_time_offset=1.5)

    sample_rate = 16000
    duration = 1.0
    samples = int(sample_rate * duration)
    threshold = int(0.05 * 32767)
    audio_data = np.full(samples, threshold - 100, dtype=np.int16)

    result = create_audio_result(audio_data, sample_rate)
    assert coordinator._validate_audio_recording(session, result) is False


def test_validation_rejects_insufficient_peak_duration():
    """Recording with RMS below threshold is rejected."""
    config = MockConfig()
    app = MockApp()
    coordinator = ProcessingCoordinator(None, None, config, app)

    session = create_session(start_time_offset=1.5)

    sample_rate = 16000
    rms_threshold = int(0.02 * 32767)
    total_samples = int(1.0 * sample_rate)

    audio_data = np.zeros(total_samples, dtype=np.int16)
    audio_data[:1000] = rms_threshold - 100

    result = create_audio_result(audio_data, sample_rate)
    assert coordinator._validate_audio_recording(session, result) is False


def test_validation_passes_with_sustained_peak():
    """Recording with sustained peak above threshold for 500ms passes."""
    config = MockConfig()
    app = MockApp()
    coordinator = ProcessingCoordinator(None, None, config, app)

    session = create_session(start_time_offset=1.5)

    sample_rate = 16000
    threshold = int(0.05 * 32767)
    peak_samples = int(0.6 * sample_rate)
    total_samples = int(1.0 * sample_rate)

    audio_data = np.zeros(total_samples, dtype=np.int16)
    audio_data[:peak_samples] = threshold + 100

    result = create_audio_result(audio_data, sample_rate)
    assert coordinator._validate_audio_recording(session, result) is True


def test_validation_handles_multi_channel_audio():
    """Validation flattens multi-channel audio correctly."""
    config = MockConfig()
    app = MockApp()
    coordinator = ProcessingCoordinator(None, None, config, app)

    session = create_session(start_time_offset=1.5)

    sample_rate = 16000
    duration = 1.0
    samples = int(sample_rate * duration)
    audio_data = np.full((samples, 2), 3000, dtype=np.int16)

    result = create_audio_result(audio_data, sample_rate)
    assert coordinator._validate_audio_recording(session, result) is True


def test_validation_ignores_non_audio_data_results():
    """Non-AudioDataResult types pass validation without checks."""
    config = MockConfig()
    app = MockApp()
    coordinator = ProcessingCoordinator(None, None, config, app)

    session = create_session(start_time_offset=0.1)

    from audio_source import AudioResult
    result = AudioResult("other_type", 16000)

    assert coordinator._validate_audio_recording(session, result) is True


def test_validation_with_intermittent_peaks():
    """Recording with sparse brief peaks passes RMS validation."""
    config = MockConfig()
    app = MockApp()
    coordinator = ProcessingCoordinator(None, None, config, app)

    session = create_session(start_time_offset=1.5)

    sample_rate = 16000
    threshold = int(0.05 * 32767)
    total_samples = int(1.0 * sample_rate)

    audio_data = np.zeros(total_samples, dtype=np.int16)
    audio_data[0:1000] = threshold + 100
    audio_data[2000:3000] = threshold + 100
    audio_data[4000:5000] = threshold + 100

    result = create_audio_result(audio_data, sample_rate)
    assert coordinator._validate_audio_recording(session, result) is True


if __name__ == "__main__":
    test_validation_passes_with_valid_recording()
    test_validation_rejects_too_short_duration()
    test_validation_rejects_low_amplitude()
    test_validation_rejects_insufficient_peak_duration()
    test_validation_passes_with_sustained_peak()
    test_validation_handles_multi_channel_audio()
    test_validation_ignores_non_audio_data_results()
    test_validation_with_intermittent_peaks()
    print("All audio validation tests passed")
