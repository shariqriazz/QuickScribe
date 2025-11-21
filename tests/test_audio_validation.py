"""Tests for audio recording validation in MicrophoneAudioSource."""

import time
import numpy as np
from unittest.mock import Mock, MagicMock
from microphone_audio_source import MicrophoneAudioSource
from audio_source import AudioDataResult


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


def create_audio_source(config):
    """Create MicrophoneAudioSource for testing."""
    audio_source = MicrophoneAudioSource(config)
    audio_source.recording_start_time = time.time()
    return audio_source


def test_validation_passes_with_valid_recording():
    """Valid recording with sufficient duration, amplitude, and peak duration passes."""
    config = MockConfig()
    audio_source = create_audio_source(config)
    audio_source.recording_start_time = time.time() - 1.5

    sample_rate = 16000
    duration = 1.0
    samples = int(sample_rate * duration)
    audio_data = np.full(samples, 3000, dtype=np.int16)

    assert audio_source._validate_recording(audio_data) is True


def test_validation_rejects_too_short_duration():
    """Recording shorter than minimum duration is rejected."""
    config = MockConfig()
    audio_source = create_audio_source(config)
    audio_source.recording_start_time = time.time() - 0.5

    sample_rate = 16000
    duration = 0.5
    samples = int(sample_rate * duration)
    audio_data = np.full(samples, 3000, dtype=np.int16)

    assert audio_source._validate_recording(audio_data) is False


def test_validation_rejects_low_amplitude():
    """Recording with amplitude below threshold is rejected."""
    config = MockConfig()
    audio_source = create_audio_source(config)
    audio_source.recording_start_time = time.time() - 1.5

    sample_rate = 16000
    duration = 1.0
    samples = int(sample_rate * duration)
    threshold = int(0.05 * 32767)
    audio_data = np.full(samples, threshold - 100, dtype=np.int16)

    assert audio_source._validate_recording(audio_data) is False


def test_validation_rejects_insufficient_peak_duration():
    """Recording with RMS below threshold is rejected."""
    config = MockConfig()
    audio_source = create_audio_source(config)
    audio_source.recording_start_time = time.time() - 1.5

    sample_rate = 16000
    rms_threshold = int(0.02 * 32767)
    total_samples = int(1.0 * sample_rate)

    audio_data = np.zeros(total_samples, dtype=np.int16)
    audio_data[:1000] = rms_threshold - 100

    assert audio_source._validate_recording(audio_data) is False


def test_validation_passes_with_sustained_peak():
    """Recording with sustained peak above threshold for 500ms passes."""
    config = MockConfig()
    audio_source = create_audio_source(config)
    audio_source.recording_start_time = time.time() - 1.5

    sample_rate = 16000
    threshold = int(0.05 * 32767)
    peak_samples = int(0.6 * sample_rate)
    total_samples = int(1.0 * sample_rate)

    audio_data = np.zeros(total_samples, dtype=np.int16)
    audio_data[:peak_samples] = threshold + 100

    assert audio_source._validate_recording(audio_data) is True


def test_validation_handles_multi_channel_audio():
    """Validation flattens multi-channel audio correctly."""
    config = MockConfig()
    audio_source = create_audio_source(config)
    audio_source.recording_start_time = time.time() - 1.5

    sample_rate = 16000
    duration = 1.0
    samples = int(sample_rate * duration)
    audio_data = np.full((samples, 2), 3000, dtype=np.int16)

    assert audio_source._validate_recording(audio_data) is True


def test_processing_coordinator_validates_empty_results():
    """ProcessingCoordinator rejects empty audio results."""
    import sys
    from unittest.mock import MagicMock

    sys.modules['ui'] = MagicMock()
    sys.modules['ui.posix_signal_bridge'] = MagicMock()

    from processing_coordinator import ProcessingCoordinator

    config = MockConfig()
    app = MockApp()
    coordinator = ProcessingCoordinator(None, None, config, app)

    empty_result = AudioDataResult(audio_data=np.array([], dtype=np.int16), sample_rate=16000)
    assert coordinator._validate_audio_recording(empty_result) is False

    valid_result = AudioDataResult(audio_data=np.array([100, 200], dtype=np.int16), sample_rate=16000)
    assert coordinator._validate_audio_recording(valid_result) is True


def test_validation_with_intermittent_peaks():
    """Recording with sparse brief peaks passes RMS validation."""
    config = MockConfig()
    audio_source = create_audio_source(config)
    audio_source.recording_start_time = time.time() - 1.5

    sample_rate = 16000
    threshold = int(0.05 * 32767)
    total_samples = int(1.0 * sample_rate)

    audio_data = np.zeros(total_samples, dtype=np.int16)
    audio_data[0:1000] = threshold + 100
    audio_data[2000:3000] = threshold + 100
    audio_data[4000:5000] = threshold + 100

    assert audio_source._validate_recording(audio_data) is True


def test_validation_handles_float32_audio():
    """Validation correctly handles float32 audio with normalized values."""
    config = MockConfig()
    audio_source = create_audio_source(config)
    audio_source.recording_start_time = time.time() - 1.5

    sample_rate = 16000
    duration = 1.0
    samples = int(sample_rate * duration)
    audio_data = np.full(samples, 0.05, dtype=np.float32)

    assert audio_source._validate_recording(audio_data) is True


def test_validation_rejects_low_amplitude_float32():
    """Float32 audio below threshold is rejected."""
    config = MockConfig()
    audio_source = create_audio_source(config)
    audio_source.recording_start_time = time.time() - 1.5

    sample_rate = 16000
    duration = 1.0
    samples = int(sample_rate * duration)
    audio_data = np.full(samples, 0.02, dtype=np.float32)

    assert audio_source._validate_recording(audio_data) is False


def test_dtype_max_values_all_supported_types():
    """All supported dtypes have correct max values in DTYPE_MAX_VALUES."""
    config = MockConfig()
    audio_source = create_audio_source(config)

    expected_max_values = {
        np.dtype('int8'): 127,
        np.dtype('int16'): 32767,
        np.dtype('int32'): 2147483647,
        np.dtype('uint8'): 255,
        np.dtype('uint16'): 65535,
        np.dtype('uint32'): 4294967295,
        np.dtype('float32'): 1.0,
        np.dtype('float64'): 1.0,
    }

    for dtype, expected_max in expected_max_values.items():
        actual_max = audio_source._get_max_value_for_dtype(dtype)
        assert actual_max == expected_max, f"Max value for {dtype} should be {expected_max}, got {actual_max}"


def test_dtype_max_value_unsupported_type_raises_error():
    """Unsupported dtype raises ValueError with guidance message."""
    config = MockConfig()
    audio_source = create_audio_source(config)

    try:
        audio_source._get_max_value_for_dtype(np.dtype('float16'))
        assert False, "Should have raised ValueError for unsupported dtype"
    except ValueError as e:
        error_msg = str(e)
        assert "Unsupported audio dtype: float16" in error_msg
        assert "Supported types:" in error_msg
        assert "int16" in error_msg
        assert "float32" in error_msg
        assert "To add support, add max_value mapping to DTYPE_MAX_VALUES constant" in error_msg


def test_validation_works_with_int8_audio():
    """Validation correctly handles int8 audio."""
    config = MockConfig()
    audio_source = create_audio_source(config)
    audio_source.recording_start_time = time.time() - 1.5

    sample_rate = 16000
    duration = 1.0
    samples = int(sample_rate * duration)
    threshold = int(0.05 * 127)
    audio_data = np.full(samples, threshold + 10, dtype=np.int8)

    assert audio_source._validate_recording(audio_data) is True


def test_validation_works_with_uint8_audio():
    """Validation correctly handles uint8 audio."""
    config = MockConfig()
    audio_source = create_audio_source(config)
    audio_source.recording_start_time = time.time() - 1.5

    sample_rate = 16000
    duration = 1.0
    samples = int(sample_rate * duration)
    threshold = int(0.05 * 255)
    audio_data = np.full(samples, threshold + 10, dtype=np.uint8)

    assert audio_source._validate_recording(audio_data) is True


def test_validation_works_with_int32_audio():
    """Validation correctly handles int32 audio."""
    config = MockConfig()
    audio_source = create_audio_source(config)
    audio_source.recording_start_time = time.time() - 1.5

    sample_rate = 16000
    duration = 1.0
    samples = int(sample_rate * duration)
    threshold = int(0.05 * 2147483647)
    audio_data = np.full(samples, threshold + 1000, dtype=np.int32)

    assert audio_source._validate_recording(audio_data) is True


def test_validation_works_with_float64_audio():
    """Validation correctly handles float64 audio."""
    config = MockConfig()
    audio_source = create_audio_source(config)
    audio_source.recording_start_time = time.time() - 1.5

    sample_rate = 16000
    duration = 1.0
    samples = int(sample_rate * duration)
    audio_data = np.full(samples, 0.06, dtype=np.float64)

    assert audio_source._validate_recording(audio_data) is True


if __name__ == "__main__":
    test_validation_passes_with_valid_recording()
    test_validation_rejects_too_short_duration()
    test_validation_rejects_low_amplitude()
    test_validation_rejects_insufficient_peak_duration()
    test_validation_passes_with_sustained_peak()
    test_validation_handles_multi_channel_audio()
    test_processing_coordinator_validates_empty_results()
    test_validation_with_intermittent_peaks()
    test_validation_handles_float32_audio()
    test_validation_rejects_low_amplitude_float32()
    test_dtype_max_values_all_supported_types()
    test_dtype_max_value_unsupported_type_raises_error()
    test_validation_works_with_int8_audio()
    test_validation_works_with_uint8_audio()
    test_validation_works_with_int32_audio()
    test_validation_works_with_float64_audio()
    print("All audio validation tests passed")
