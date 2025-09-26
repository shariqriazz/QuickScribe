"""Audio recording and processing module for QuickScribe."""

import sounddevice as sd
import soundfile as sf
import numpy as np
import threading
import queue
import sys
from typing import Callable, Optional


class AudioHandler:
    """Handles audio recording and processing."""
    
    def __init__(self, config, dtype: str = 'int16'):
        self.config = config
        self.dtype = dtype
        self.is_recording = False
        self.audio_queue = queue.Queue()
        self.recording_stream = None
        self.trigger_key_name = None
        
    def set_trigger_key_name(self, trigger_key_name: Optional[str]):
        """Set the trigger key name for user feedback."""
        self.trigger_key_name = trigger_key_name
        
    def audio_callback(self, indata, frames, time, status):
        """This is called (from a separate thread) for each audio block."""
        if status:
            if status.input_overflow:
                print("W", end='', flush=True)  # Indicate overflow warning
            else:
                print(f"\nAudio callback status: {status}", file=sys.stderr)
        if self.is_recording:
            self.audio_queue.put(indata.copy())

    def start_recording(self):
        """Starts the audio recording stream."""
        if self.is_recording:
            return

        print("\nRecording started... ", end='', flush=True)
        self.is_recording = True
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
            self.is_recording = False
            self.recording_stream = None
        except Exception as e:
            print(f"\nUnexpected error during recording start: {e}", file=sys.stderr)
            self.is_recording = False
            self.recording_stream = None

    def stop_recording_and_process(self, process_audio_callback: Callable[[np.ndarray], None]):
        """Stops recording and processes the audio in a separate thread."""
        if not self.is_recording:
            return

        print("Stopped. Processing... ", end='', flush=True)
        self.is_recording = False

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
            self._show_recording_prompt()
            return

        try:
            full_audio = np.concatenate(audio_data, axis=0)
        except ValueError as e:
            print(f"\nError concatenating audio data: {e}", file=sys.stderr)
            self._show_recording_prompt()
            return
        except Exception as e:
            print(f"\nUnexpected error combining audio: {e}", file=sys.stderr)
            self._show_recording_prompt()
            return

        processing_thread = threading.Thread(target=process_audio_callback, args=(full_audio,))
        processing_thread.daemon = True
        processing_thread.start()
        
    def _show_recording_prompt(self):
        """Show appropriate recording prompt based on trigger configuration."""
        if self.trigger_key_name is not None:
            print(f"\nHold '{self.trigger_key_name}' to record...")
        else:
            print("\nKeyboard trigger disabled. Use SIGUSR1 to start and SIGUSR2 to stop.")
            
    def test_audio_device(self):
        """Test if audio device is working."""
        try:
            with sd.InputStream(
                samplerate=self.config.sample_rate,
                channels=self.config.channels,
                dtype=self.dtype,
                callback=lambda i,f,t,s: None
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
            
    def cleanup(self):
        """Clean up audio resources."""
        if self.recording_stream:
            try:
                if self.recording_stream.active:
                    self.recording_stream.stop()
                self.recording_stream.close()
                print("Audio stream stopped.")
            except Exception:
                pass  # Ignore errors on final cleanup