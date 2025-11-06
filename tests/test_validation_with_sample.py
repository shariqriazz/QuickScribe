#!/usr/bin/env python
"""Test audio validation with sample audio file."""

import time
import numpy as np
import wave
from processing_coordinator import ProcessingCoordinator
from recording_session import RecordingSession, RecordingSource
from audio_source import AudioDataResult
from config_manager import ConfigManager


class MockApp:
    """Mock application for testing."""

    def _return_to_idle(self):
        print("App: returned to idle")

    def _update_tray_state(self, state):
        print(f"App: tray state = {state}")

    def _show_recording_prompt(self):
        print("App: showing recording prompt")


def load_wav_file(filepath):
    """Load WAV file and return audio data and sample rate."""
    with wave.open(filepath, 'rb') as wf:
        sample_rate = wf.getframerate()
        n_frames = wf.getnframes()
        audio_bytes = wf.readframes(n_frames)

        if wf.getsampwidth() == 2:
            audio_data = np.frombuffer(audio_bytes, dtype=np.int16)
        else:
            raise ValueError(f"Unsupported sample width: {wf.getsampwidth()}")

        if wf.getnchannels() == 2:
            audio_data = audio_data.reshape(-1, 2)

        return audio_data, sample_rate


def test_sample_file(filepath):
    """Test validation on sample audio file."""
    print(f"\nTesting: {filepath}")
    print("=" * 60)

    config = ConfigManager()
    app = MockApp()
    coordinator = ProcessingCoordinator(None, None, config, app)

    audio_data, sample_rate = load_wav_file(filepath)

    print(f"Audio info:")
    print(f"  Sample rate: {sample_rate} Hz")
    print(f"  Duration: {len(audio_data) / sample_rate:.2f}s")
    print(f"  Shape: {audio_data.shape}")
    print(f"  Data type: {audio_data.dtype}")

    session = RecordingSession(RecordingSource.KEYBOARD)
    session.start_time = time.time() - (len(audio_data) / sample_rate)

    result = AudioDataResult(audio_data=audio_data, sample_rate=sample_rate)

    print(f"\nValidation thresholds:")
    print(f"  min_recording_duration: {config.min_recording_duration}s")
    print(f"  audio_amplitude_threshold: {config.audio_amplitude_threshold} ({int(config.audio_amplitude_threshold * 32767)})")
    print(f"  min_peak_duration: {config.min_peak_duration}s")
    print(f"  min_peak_duration_amplitude_threshold: {config.min_peak_duration_amplitude_threshold} ({int(config.min_peak_duration_amplitude_threshold * 32767)})")

    print(f"\nRunning validation...")
    is_valid = coordinator._validate_audio_recording(session, result)

    print(f"\nResult: {'PASS' if is_valid else 'FAIL'}")
    print("=" * 60)

    return is_valid


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        filepath = sys.argv[1]
    else:
        filepath = "samples/sumtest.wav"

    test_sample_file(filepath)
