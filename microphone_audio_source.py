"""Microphone audio source implementation for QuickScribe."""

import sounddevice as sd
import numpy as np
import queue
import sys
import time
from typing import Optional
from audio_source import AudioSource, AudioResult, AudioDataResult, AudioChunkHandler, DefaultAudioChunkHandler
from lib.pr_log import pr_emerg, pr_err, pr_warn, pr_info, pr_debug


class MicrophoneAudioSource(AudioSource):
    """Handles microphone audio recording using sounddevice."""

    DTYPE_MAX_VALUES = {
        np.dtype('int8'): 127,
        np.dtype('int16'): 32767,
        np.dtype('int32'): 2147483647,
        np.dtype('uint8'): 255,
        np.dtype('uint16'): 65535,
        np.dtype('uint32'): 4294967295,
        np.dtype('float32'): 1.0,
        np.dtype('float64'): 1.0,
    }

    def __init__(self, config, dtype: str = 'int16', chunk_handler: Optional[AudioChunkHandler] = None):
        super().__init__(config)
        self.dtype = dtype
        self._is_recording = False
        self.audio_queue = queue.Queue()
        self.recording_stream = None
        self.chunk_handler = chunk_handler or DefaultAudioChunkHandler()
        self.recording_start_time = None

    def _get_max_value_for_dtype(self, dtype: np.dtype) -> float:
        """
        Get maximum amplitude value for audio dtype.

        Args:
            dtype: numpy dtype of audio data

        Returns:
            Maximum amplitude value for the dtype

        Raises:
            ValueError: If dtype is not supported
        """
        if dtype not in self.DTYPE_MAX_VALUES:
            supported = ', '.join(str(dt) for dt in self.DTYPE_MAX_VALUES.keys())
            raise ValueError(
                f"Unsupported audio dtype: {dtype}. "
                f"Supported types: {supported}. "
                f"To add support, add max_value mapping to DTYPE_MAX_VALUES constant."
            )
        return self.DTYPE_MAX_VALUES[dtype]

    def initialize(self) -> bool:
        """Initialize the microphone audio source."""
        try:
            if self.test_audio_device():
                self._initialized = True
                return True
            return False
        except Exception as e:
            pr_err(f"Error initializing microphone audio source: {e}")
            return False

    def audio_callback(self, indata, frames, time_info, status):
        """This is called (from a separate thread) for each audio block."""
        if status:
            if status.input_overflow:
                pr_warn("Audio buffer overflow")
            else:
                pr_warn(f"Audio callback status: {status}")

        if self._is_recording:
            chunk_copy = indata.copy()
            # Allow handler to intercept chunk
            self.chunk_handler.on_chunk(chunk_copy, time_info.currentTime if time_info else 0.0)
            # Store for final result
            self.audio_queue.put(chunk_copy)

    def start_recording(self) -> None:
        """Starts the audio recording stream."""
        if self._is_recording:
            return

        pr_info("Recording started...")
        self._is_recording = True
        self.recording_start_time = time.time()
        self.audio_queue.queue.clear()

        try:
            self.recording_stream = sd.InputStream(
                samplerate=self.config.sample_rate,
                channels=self.config.channels,
                dtype=self.dtype,
                callback=self.audio_callback
            )
            self.recording_stream.start()
        except sd.PortAudioError as e:
            pr_err(f"Error starting audio stream: {e}")
            pr_err("Check audio device settings and permissions.")
            self._is_recording = False
            self.recording_stream = None
        except Exception as e:
            pr_err(f"Unexpected error during recording start: {e}")
            self._is_recording = False
            self.recording_stream = None

    def stop_recording(self) -> AudioResult:
        """Stops recording and returns the audio result."""
        if not self._is_recording:
            # Return empty result if not recording
            return AudioDataResult(
                audio_data=np.array([], dtype=self.dtype),
                sample_rate=self.config.sample_rate
            )

        pr_info("Stopped. Processing...")
        self._is_recording = False

        if self.recording_stream:
            try:
                self.recording_stream.stop()
                self.recording_stream.close()
            except sd.PortAudioError as e:
                pr_err(f"Error stopping/closing audio stream: {e}")
            except Exception as e:
                pr_err(f"Unexpected error stopping/closing audio stream: {e}")
            finally:
                self.recording_stream = None

        audio_data = []
        while not self.audio_queue.empty():
            try:
                audio_data.append(self.audio_queue.get_nowait())
            except queue.Empty:
                break

        if not audio_data:
            pr_info("No audio data recorded.")
            return AudioDataResult(
                audio_data=np.array([], dtype=self.dtype),
                sample_rate=self.config.sample_rate
            )

        try:
            full_audio = np.concatenate(audio_data, axis=0)
        except ValueError as e:
            pr_err(f"Error concatenating audio data: {e}")
            return AudioDataResult(
                audio_data=np.array([], dtype=self.dtype),
                sample_rate=self.config.sample_rate
            )
        except Exception as e:
            pr_err(f"Unexpected error combining audio: {e}")
            return AudioDataResult(
                audio_data=np.array([], dtype=self.dtype),
                sample_rate=self.config.sample_rate
            )

        pr_debug(f"Audio data: chunks={len(audio_data)} shape={full_audio.shape} dtype={full_audio.dtype} min={np.min(full_audio)} max={np.max(full_audio)} samples={len(full_audio)}")

        if not self._validate_recording(full_audio):
            return AudioDataResult(
                audio_data=np.array([], dtype=self.dtype),
                sample_rate=self.config.sample_rate
            )

        return AudioDataResult(
            audio_data=full_audio,
            sample_rate=self.config.sample_rate
        )

    def is_recording(self) -> bool:
        """Check if currently recording."""
        return self._is_recording

    def _validate_recording(self, audio_data: np.ndarray) -> bool:
        """
        Validate audio recording meets minimum quality requirements.

        Checks:
        - Duration meets minimum threshold
        - Peak amplitude exceeds threshold
        - RMS peak over sliding window exceeds threshold

        Returns:
            True if recording is valid, False if should be discarded
        """
        recording_duration = time.time() - self.recording_start_time
        if recording_duration < self.config.min_recording_duration:
            pr_warn(f"Recording discarded: too short ({recording_duration:.2f}s < {self.config.min_recording_duration}s)")
            return False

        max_value = self._get_max_value_for_dtype(audio_data.dtype)

        abs_audio = np.abs(audio_data.flatten())
        peak_amplitude = np.max(abs_audio)

        threshold = self.config.audio_amplitude_threshold * max_value
        if np.issubdtype(audio_data.dtype, np.integer):
            threshold = int(threshold)

        if peak_amplitude < threshold:
            peak_percent = (peak_amplitude / max_value) * 100
            threshold_percent = self.config.audio_amplitude_threshold * 100
            pr_warn(f"Recording discarded: amplitude too low ({peak_percent:.1f}% < {threshold_percent:.1f}%)")
            return False

        window_size = int(self.config.min_peak_duration * self.config.sample_rate)

        rms_threshold = self.config.min_peak_duration_amplitude_threshold * max_value
        if np.issubdtype(audio_data.dtype, np.integer):
            rms_threshold = int(rms_threshold)

        if len(abs_audio) < window_size:
            pr_warn(f"Recording discarded: audio too short for RMS window analysis")
            return False

        audio_flat = audio_data.flatten().astype(np.float64)
        step_size = max(1, window_size // 10)

        num_windows = (len(audio_flat) - window_size) // step_size + 1
        rms_values = np.zeros(num_windows)

        for i in range(num_windows):
            start = i * step_size
            end = start + window_size
            window = audio_flat[start:end]
            rms_values[i] = np.sqrt(np.mean(window ** 2))

        peak_rms = np.max(rms_values)
        peak_rms_percent = (peak_rms / max_value) * 100
        rms_threshold_percent = self.config.min_peak_duration_amplitude_threshold * 100

        if peak_rms < rms_threshold:
            pr_warn(f"Recording discarded: RMS peak too low ({peak_rms_percent:.1f}% < {rms_threshold_percent:.1f}%)")
            return False

        windows_above = np.sum(rms_values >= rms_threshold)
        pr_debug(f"Audio validation: duration={recording_duration:.2f}s peak={peak_amplitude} ({(peak_amplitude/max_value)*100:.1f}%) rms={peak_rms:.1f} ({peak_rms_percent:.1f}%) windows={windows_above}/{len(rms_values)}")
        return True

    def test_audio_device(self):
        """Test if audio device is working."""
        try:
            with sd.InputStream(
                samplerate=self.config.sample_rate,
                channels=self.config.channels,
                dtype=self.dtype,
                callback=lambda i, f, t, s: None
            ):
                pass
            pr_info("Audio device check successful.")
            return True
        except sd.PortAudioError as e:
            pr_emerg(f"Audio device error: {e}")
            pr_emerg("Please check connection, selection, and permissions.")
            return False
        except Exception as e:
            pr_warn(f"Could not query/test audio devices: {e}")
            return False

    def _cleanup(self):
        """Clean up audio resources."""
        if self.recording_stream:
            try:
                if self.recording_stream.active:
                    self.recording_stream.stop()
                self.recording_stream.close()
                pr_info("Audio stream stopped.")
            except Exception:
                pass