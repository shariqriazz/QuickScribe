"""Microphone audio source implementation for QuickScribe."""

import sounddevice as sd
import numpy as np
import queue
import sys
from typing import Optional
from audio_source import AudioSource, AudioResult, AudioDataResult, AudioChunkHandler, DefaultAudioChunkHandler


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
            print(f"Error initializing microphone audio source: {e}", file=sys.stderr)
            return False

    def audio_callback(self, indata, frames, time_info, status):
        """This is called (from a separate thread) for each audio block."""
        if status:
            if status.input_overflow:
                print("W", end='', flush=True)  # Indicate overflow warning
            else:
                print(f"\nAudio callback status: {status}", file=sys.stderr)

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

        print("\nRecording started... ", end='', flush=True)
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
            print(f"\nError starting audio stream: {e}", file=sys.stderr)
            print("Check audio device settings and permissions.", file=sys.stderr)
            self._is_recording = False
            self.recording_stream = None
        except Exception as e:
            print(f"\nUnexpected error during recording start: {e}", file=sys.stderr)
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

        print("Stopped. Processing... ", end='', flush=True)
        self._is_recording = False

        if self.recording_stream:
            try:
                self.recording_stream.stop()
                self.recording_stream.close()
            except sd.PortAudioError as e:
                print(f"\nError stopping/closing audio stream: {e}", file=sys.stderr)
            except Exception as e:
                print(f"\nUnexpected error stopping/closing audio stream: {e}", file=sys.stderr)
            finally:
                self.recording_stream = None

        audio_data = []
        while not self.audio_queue.empty():
            try:
                audio_data.append(self.audio_queue.get_nowait())
            except queue.Empty:
                break

        if not audio_data:
            print("No audio data recorded.")
            return AudioDataResult(
                audio_data=np.array([], dtype=self.dtype),
                sample_rate=self.config.sample_rate
            )

        try:
            full_audio = np.concatenate(audio_data, axis=0)
        except ValueError as e:
            print(f"\nError concatenating audio data: {e}", file=sys.stderr)
            return AudioDataResult(
                audio_data=np.array([], dtype=self.dtype),
                sample_rate=self.config.sample_rate
            )
        except Exception as e:
            print(f"\nUnexpected error combining audio: {e}", file=sys.stderr)
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
            print("Audio device check successful.")
            return True
        except sd.PortAudioError as e:
            print(f"\nFATAL: Audio device error: {e}", file=sys.stderr)
            print("Please check connection, selection, and permissions.", file=sys.stderr)
            return False
        except Exception as e:
            print(f"\nWarning: Could not query/test audio devices: {e}", file=sys.stderr)
            return False

    def _cleanup(self):
        """Clean up audio resources."""
        if self.recording_stream:
            try:
                if self.recording_stream.active:
                    self.recording_stream.stop()
                self.recording_stream.close()
                print("Audio stream stopped.")
            except Exception:
                pass  # Ignore errors on final cleanup