"""Microphone audio source implementation for QuickScribe."""

import sounddevice as sd
import numpy as np
import queue
import sys
from typing import Optional
from audio_source import AudioSource, AudioResult, AudioDataResult, AudioChunkHandler, DefaultAudioChunkHandler
from lib.pr_log import pr_emerg, pr_err, pr_warn, pr_info


class MicrophoneAudioSource(AudioSource):
    """Handles microphone audio recording using sounddevice."""

    def __init__(self, config, dtype: str = 'int16', chunk_handler: Optional[AudioChunkHandler] = None):
        super().__init__(config)
        self.dtype = dtype
        self._is_recording = False
        self.audio_queue = queue.Queue()
        self.recording_stream = None
        self.chunk_handler = chunk_handler or DefaultAudioChunkHandler()

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

        return AudioDataResult(
            audio_data=full_audio,
            sample_rate=self.config.sample_rate
        )

    def is_recording(self) -> bool:
        """Check if currently recording."""
        return self._is_recording


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