"""VOSK-based transcription implementation for QuickScribe."""

import json
import os
import sys
import numpy as np
from typing import Optional

try:
    import vosk
except ImportError:
    vosk = None

from audio_source import AudioChunkHandler
from transcription.base import TranscriptionAudioSource, parse_transcription_model
from lib.pr_log import pr_err, pr_warn, pr_info, get_streaming_handler


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
            self.model = self._load_vosk_model(model_path)
            self.recognizer = vosk.KaldiRecognizer(self.model, sample_rate)

            # Set L-graph if provided
            if lgraph_path:
                try:
                    with open(lgraph_path, 'r') as f:
                        grammar = f.read()
                    self.recognizer.SetGrammar(grammar)
                except Exception as e:
                    pr_warn(f"Failed to load L-graph from {lgraph_path}: {e}")

        except Exception as e:
            raise RuntimeError(f"Failed to initialize VOSK model from {model_path}: {e}")

        # Transcription state
        self.partial_results = []
        self.final_text = ""
        self.is_complete = False

        # Streaming handler for partial results (maintained across chunks)
        self.stream_handler = None

    def _load_vosk_model(self, model_identifier: str) -> vosk.Model:
        """
        Load VOSK model from local path or download by name.

        Supports:
        - Relative paths: ./models/vosk-model or models/vosk-model
        - Absolute paths: /usr/share/vosk/model
        - Home paths: ~/models/vosk-model
        - Model names: vosk-model-small-en-us-0.15 (auto-download)

        Args:
            model_identifier: Local path or model name for download

        Returns:
            Loaded VOSK model

        Raises:
            RuntimeError: If model loading fails
        """
        expanded_path = os.path.expanduser(model_identifier)
        abs_path = os.path.abspath(expanded_path)
        model = None
        model_source = None

        if os.path.exists(expanded_path):
            try:
                model = vosk.Model(expanded_path)
                model_source = f"local path: {abs_path}"
            except Exception as e:
                raise RuntimeError(f"Failed to load VOSK model from local path {abs_path}: {e}")
        else:
            try:
                model = vosk.Model(model_name=model_identifier)
                cache_path = os.path.expanduser(f"~/.cache/vosk/{model_identifier}")
                model_source = f"model name: {model_identifier} (cached at {cache_path})"
            except Exception as e:
                raise RuntimeError(
                    f"Failed to load VOSK model '{model_identifier}' "
                    f"(not found locally, download failed): {e}"
                )

        pr_info(f"VOSK model loaded from {model_source}")
        return model

    def end_streaming(self):
        """
        End streaming if active.

        Single point of truth for stream cleanup.
        """
        if self.stream_handler is not None:
            self.stream_handler.__exit__(None, None, None)
            self.stream_handler = None

    def reset(self):
        """Reset handler for new recording."""
        self.end_streaming()

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
                    pr_warn(f"Failed to reload L-graph during reset: {e}")
        except Exception as e:
            pr_err(f"Error resetting VOSK recognizer: {e}")

    def on_chunk(self, chunk: np.ndarray, timestamp: float) -> None:
        """Process audio chunk through VOSK recognizer."""
        try:
            if chunk.dtype != np.int16:
                chunk = chunk.astype(np.int16)
            audio_bytes = chunk.tobytes()

            # Start streaming on first chunk
            if self.stream_handler is None:
                self.stream_handler = get_streaming_handler()
                self.stream_handler.__enter__()

            if self.recognizer.AcceptWaveform(audio_bytes):
                result = json.loads(self.recognizer.Result())
                if result.get('text'):
                    self.final_text += result['text'] + " "
                    self.stream_handler.write_full(self.final_text)
            else:
                partial = json.loads(self.recognizer.PartialResult())
                if partial.get('partial'):
                    temp_display = self.final_text + partial['partial']
                    self.stream_handler.write_full(temp_display)

        except Exception as e:
            pr_err(f"Error processing audio chunk in VOSK: {e}")

    def finalize(self) -> str:
        """Get final transcription result."""
        try:
            self.end_streaming()

            # Get any remaining final result
            final_result = json.loads(self.recognizer.FinalResult())
            if final_result.get('text'):
                self.final_text += final_result['text']

            self.is_complete = True
            return self.final_text.strip()

        except Exception as e:
            pr_err(f"Error finalizing VOSK transcription: {e}")
            return self.final_text.strip()


class VoskTranscriptionAudioSource(TranscriptionAudioSource):
    """VOSK transcription implementation with streaming support."""

    def __init__(self, config, transcription_model: str):
        import os
        model_identifier = parse_transcription_model(transcription_model)
        model_path = os.path.expanduser(model_identifier)
        lgraph_path = getattr(config, 'vosk_lgraph_path', None)

        vosk_handler = VoskChunkHandler(model_path, config.sample_rate, lgraph_path)

        super().__init__(config, model_path, supports_streaming=True, dtype='int16', chunk_handler=vosk_handler)

        self.lgraph_path = lgraph_path
        self.vosk_handler = vosk_handler

    def _transcribe_audio(self, audio_data: np.ndarray) -> str:
        """Transcribe audio using VOSK streaming handler."""
        return self.vosk_handler.finalize()

    def initialize(self) -> bool:
        """Initialize VOSK transcription source."""
        try:
            if vosk is None:
                pr_err("VOSK library not available")
                return False

            if not super().initialize():
                return False

            pr_info(f"VOSK initialized with model: {self.model_identifier}")
            if self.lgraph_path:
                pr_info(f"L-graph enabled: {self.lgraph_path}")

            return True

        except Exception as e:
            pr_err(f"Error initializing VOSK: {e}")
            return False

    def start_recording(self) -> None:
        """Start recording and reset VOSK handler for fresh transcription."""
        # Reset VOSK handler to clear any previous transcription
        self.vosk_handler.reset()

        # Call parent to start the actual recording
        super().start_recording()