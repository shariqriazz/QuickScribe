"""VOSK-based audio source implementation for QuickScribe."""

import json
import sys
import numpy as np
from typing import Optional

try:
    import vosk
except ImportError:
    vosk = None

from audio_source import AudioChunkHandler, AudioResult, AudioTextResult
from microphone_audio_source import MicrophoneAudioSource


class VoskChunkHandler(AudioChunkHandler):
    """Handles real-time transcription using VOSK recognizer."""

    def __init__(self, model_path: str, sample_rate: int, lgraph_path: Optional[str] = None):
        if vosk is None:
            raise ImportError("VOSK library not installed. Install with: pip install vosk")

        self.sample_rate = sample_rate
        self.model_path = model_path
        self.lgraph_path = lgraph_path

        # Initialize VOSK model and recognizer
        try:
            vosk.SetLogLevel(-1)  # Reduce VOSK logging
            self.model = vosk.Model(model_path)
            self.recognizer = vosk.KaldiRecognizer(self.model, sample_rate)

            # Set L-graph if provided
            if lgraph_path:
                try:
                    with open(lgraph_path, 'r') as f:
                        grammar = f.read()
                    self.recognizer.SetGrammar(grammar)
                except Exception as e:
                    print(f"Warning: Failed to load L-graph from {lgraph_path}: {e}", file=sys.stderr)

        except Exception as e:
            raise RuntimeError(f"Failed to initialize VOSK model from {model_path}: {e}")

        # Transcription state
        self.partial_results = []
        self.final_text = ""
        self.is_complete = False

    def reset(self):
        """Reset handler for new recording."""
        # Clear transcription state
        self.final_text = ""
        self.partial_results = []
        self.is_complete = False

        # Reset VOSK recognizer for fresh audio stream
        try:
            self.recognizer = vosk.KaldiRecognizer(self.model, self.sample_rate)

            # Re-apply L-graph if configured
            if self.lgraph_path:
                try:
                    with open(self.lgraph_path, 'r') as f:
                        grammar = f.read()
                    self.recognizer.SetGrammar(grammar)
                except Exception as e:
                    print(f"Warning: Failed to reload L-graph during reset: {e}", file=sys.stderr)
        except Exception as e:
            print(f"Error resetting VOSK recognizer: {e}", file=sys.stderr)

    def on_chunk(self, chunk: np.ndarray, timestamp: float) -> None:
        """Process audio chunk through VOSK recognizer."""
        try:
            # Convert numpy array to bytes (VOSK expects bytes)
            if chunk.dtype != np.int16:
                chunk = chunk.astype(np.int16)
            audio_bytes = chunk.tobytes()

            # Feed audio to recognizer
            if self.recognizer.AcceptWaveform(audio_bytes):
                # Final result available
                result = json.loads(self.recognizer.Result())
                if result.get('text'):
                    self.final_text += result['text'] + " "
            else:
                # Partial result
                partial = json.loads(self.recognizer.PartialResult())
                if partial.get('partial'):
                    # Store partial for display but don't accumulate
                    pass

        except Exception as e:
            print(f"Error processing audio chunk in VOSK: {e}", file=sys.stderr)

    def finalize(self) -> str:
        """Get final transcription result."""
        try:
            # Get any remaining final result
            final_result = json.loads(self.recognizer.FinalResult())
            if final_result.get('text'):
                self.final_text += final_result['text']

            self.is_complete = True
            return self.final_text.strip()

        except Exception as e:
            print(f"Error finalizing VOSK transcription: {e}", file=sys.stderr)
            return self.final_text.strip()


class VoskAudioSource(MicrophoneAudioSource):
    """Audio source that performs real-time transcription using VOSK."""

    def __init__(self, config, model_path: str, lgraph_path: Optional[str] = None, dtype: str = 'int16'):
        # Create VOSK chunk handler
        vosk_handler = VoskChunkHandler(model_path, config.sample_rate, lgraph_path)

        # Initialize parent with VOSK handler
        super().__init__(config, dtype, vosk_handler)

        self.model_path = model_path
        self.lgraph_path = lgraph_path
        self.vosk_handler = vosk_handler

    def stop_recording(self) -> AudioResult:
        """Stop recording and return transcribed text result."""
        # First get the raw audio data from parent
        audio_result = super().stop_recording()

        # Check if we got audio data
        if hasattr(audio_result, 'audio_data') and len(audio_result.audio_data) > 0:
            # Finalize VOSK transcription
            transcribed_text = self.vosk_handler.finalize()

            print(f"VOSK transcribed: '{transcribed_text}'")

            # Return AudioTextResult with transcribed text and original audio
            return AudioTextResult(
                transcribed_text=transcribed_text,
                sample_rate=self.config.sample_rate,
                audio_data=audio_result.audio_data
            )
        else:
            # No audio data, return empty text result
            return AudioTextResult(
                transcribed_text="",
                sample_rate=self.config.sample_rate,
                audio_data=np.array([], dtype=self.dtype)
            )

    def initialize(self) -> bool:
        """Initialize VOSK audio source."""
        try:
            # Check if VOSK is available
            if vosk is None:
                print("Error: VOSK library not available", file=sys.stderr)
                return False

            # Initialize parent (microphone)
            if not super().initialize():
                return False

            print(f"VOSK audio source initialized with model: {self.model_path}")
            if self.lgraph_path:
                print(f"L-graph enabled: {self.lgraph_path}")

            return True

        except Exception as e:
            print(f"Error initializing VOSK audio source: {e}", file=sys.stderr)
            return False

    def start_recording(self) -> None:
        """Start recording and reset VOSK handler for fresh transcription."""
        # Reset VOSK handler to clear any previous transcription
        self.vosk_handler.reset()

        # Call parent to start the actual recording
        super().start_recording()