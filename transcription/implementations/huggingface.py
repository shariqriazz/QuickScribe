"""HuggingFace Wav2Vec2-based transcription implementation for QuickScribe."""

import os
import sys
import numpy as np
from typing import Optional
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    import torch
    import transformers
    from transformers import Wav2Vec2ForCTC, Wav2Vec2FeatureExtractor, Wav2Vec2PhonemeCTCTokenizer
    from transformers.utils import is_offline_mode
    from huggingface_hub import HfApi
except ImportError:
    torch = None
    transformers = None
    Wav2Vec2ForCTC = None
    Wav2Vec2FeatureExtractor = None
    Wav2Vec2PhonemeCTCTokenizer = None
    is_offline_mode = None
    HfApi = None

try:
    import pyrubberband as pyrb
except ImportError:
    pyrb = None

from audio_source import AudioChunkHandler, AudioResult, AudioTextResult, AudioDataResult
from transcription.base import TranscriptionAudioSource
from phoneme_mapper import process_wav2vec2_output


def format_phoneme_output(raw_phonemes: str) -> str:
    """Format phoneme output showing IPA."""
    return f"\n    IPA: {raw_phonemes.strip()}"


class Wav2Vec2ChunkHandler(AudioChunkHandler):
    """Handles real-time phoneme recognition using Wav2Vec2."""

    def __init__(self, model_path: str, sample_rate: int):
        if torch is None or transformers is None:
            raise ImportError("PyTorch and transformers libraries not installed. Install with: pip install torch transformers huggingface_hub")

        self.sample_rate = sample_rate
        self.model_path = model_path

        # Initialize Wav2Vec2 model and processor
        try:
            print(f"Loading Wav2Vec2 model: {model_path}")

            # Check if we're offline or if model exists
            is_local_path = os.path.exists(model_path)
            if not is_local_path and not is_offline_mode():
                print("Downloading from Hugging Face (this may take a moment)...")
                # Verify model exists on HF Hub
                try:
                    if HfApi:
                        api = HfApi()
                        api.model_info(model_path)
                except Exception as hf_error:
                    print(f"Warning: Could not verify model on Hugging Face: {hf_error}", file=sys.stderr)

            # Load as phoneme model (required for phoneme recognition)
            self.feature_extractor = Wav2Vec2FeatureExtractor.from_pretrained(
                model_path,
                cache_dir=None,  # Use default HF cache (~/.cache/huggingface/)
                force_download=False,  # Use cached if available
                local_files_only=is_offline_mode()  # Only use local files if offline
            )
            self.tokenizer = Wav2Vec2PhonemeCTCTokenizer.from_pretrained(
                model_path,
                cache_dir=None,  # Use default HF cache (~/.cache/huggingface/)
                force_download=False,  # Use cached if available
                local_files_only=is_offline_mode()  # Only use local files if offline
            )
            self.model = Wav2Vec2ForCTC.from_pretrained(
                model_path,
                cache_dir=None,  # Use default HF cache
                force_download=False,  # Use cached if available
                local_files_only=is_offline_mode()  # Only use local files if offline
            )
            print(f"Loaded as Wav2Vec2 Phoneme model")
            self.model.eval()  # Set to evaluation mode
            print(f"Successfully loaded Wav2Vec2 model: {model_path}")

            # Print model info
            if hasattr(self.model.config, 'vocab_size'):
                print(f"Model vocab size: {self.model.config.vocab_size}")

        except Exception as e:
            error_msg = f"Failed to load Wav2Vec2 model from {model_path}: {e}\n"
            if is_local_path:
                error_msg += "Local path exists but model loading failed. Check if it's a valid Wav2Vec2 model."
            else:
                error_msg += "Make sure the model exists on Hugging Face or provide a valid local path.\n"
                error_msg += "Popular phoneme models: facebook/wav2vec2-lv-60-espeak-cv-ft"
            raise RuntimeError(error_msg)

        # Audio accumulation for processing
        self.accumulated_audio = []
        self.phoneme_text = ""
        self.is_complete = False

    def reset(self):
        """Reset handler for new recording."""
        self.accumulated_audio = []
        self.phoneme_text = ""
        self.is_complete = False

    def on_chunk(self, chunk: np.ndarray, timestamp: float) -> None:
        """Process audio chunk and accumulate for phoneme recognition."""
        try:
            # Skip empty or very small chunks
            if chunk.size == 0 or len(chunk) < 10:
                return

            # Convert to float32 if needed
            if chunk.dtype != np.float32:
                chunk = chunk.astype(np.float32) / 32768.0  # Normalize int16 to float32

            # Accumulate audio chunks
            self.accumulated_audio.append(chunk)

        except Exception as e:
            print(f"Error processing audio chunk in Wav2Vec2: {e}", file=sys.stderr)

    def finalize(self) -> str:
        """Get final phoneme transcription result."""
        try:
            if not self.accumulated_audio:
                self.is_complete = True
                return ""

            # Concatenate all accumulated audio
            full_audio = np.concatenate(self.accumulated_audio)

            # Check minimum audio length for Wav2Vec2 (need at least 320 samples for 16kHz)
            min_samples = max(320, self.sample_rate // 50)  # At least 20ms of audio
            if len(full_audio) < min_samples:
                print(f"Audio too short for Wav2Vec2: {len(full_audio)} samples, need at least {min_samples}", file=sys.stderr)
                self.is_complete = True
                return ""

            # Process through Wav2Vec2 model
            with torch.no_grad():
                # Prepare input
                input_values = self.feature_extractor(
                    full_audio,
                    sampling_rate=self.sample_rate,
                    return_tensors="pt"
                ).input_values

                # Get model prediction
                logits = self.model(input_values).logits
                predicted_ids = torch.argmax(logits, dim=-1)

                # Decode to phonemes
                raw_phonemes = self.tokenizer.batch_decode(predicted_ids)[0]
                # Format with both IPA and alphanumeric
                self.phoneme_text = format_phoneme_output(raw_phonemes)

            self.is_complete = True
            return self.phoneme_text.strip()

        except Exception as e:
            print(f"Error finalizing Wav2Vec2 transcription: {e}", file=sys.stderr)
            self.is_complete = True
            return ""


class HuggingFaceTranscriptionAudioSource(TranscriptionAudioSource):
    """HuggingFace Wav2Vec2 transcription implementation using phoneme recognition."""

    def __init__(self, config, transcription_model: str):
        model_identifier = transcription_model.split('/', 1)[1]
        super().__init__(config, model_identifier, supports_streaming=False, dtype='float32')

        self.speed_factors = [0.80, 0.85, 0.90, 0.95]

        if pyrb is None:
            raise ImportError("pyrubberband library not installed. Install with: pip install pyrubberband")

        self._load_model(model_identifier)

    def _load_model(self, model_path: str):
        """Load Wav2Vec2 model, feature extractor, and tokenizer."""
        if torch is None or transformers is None:
            raise ImportError("PyTorch and transformers libraries not installed. Install with: pip install torch transformers huggingface_hub")

        try:
            print(f"Loading Wav2Vec2 model: {model_path}")

            # Load components
            self.feature_extractor = Wav2Vec2FeatureExtractor.from_pretrained(
                model_path,
                cache_dir=None,
                force_download=False,
                local_files_only=is_offline_mode()
            )

            # Load model
            self.model = Wav2Vec2ForCTC.from_pretrained(
                model_path,
                cache_dir=None,
                force_download=False,
                local_files_only=is_offline_mode()
            )

            # Load vocabulary for phoneme decoding
            self._load_phoneme_vocab(model_path)

            self.model.eval()
            print(f"Successfully loaded Wav2Vec2 model: {model_path}")

        except Exception as e:
            raise RuntimeError(f"Failed to load Wav2Vec2 model from {model_path}: {e}")

    def _load_phoneme_vocab(self, model_path: str):
        """Load phoneme vocabulary for decoding."""
        try:
            import json
            from huggingface_hub import hf_hub_download

            # Download vocab file
            vocab_path = hf_hub_download(repo_id=model_path, filename='vocab.json')

            with open(vocab_path, 'r') as f:
                vocab = json.load(f)

            # Create id to phoneme mapping
            self.id_to_phoneme = {int(idx): phoneme for phoneme, idx in vocab.items()}
            print(f"Wav2Vec2 phoneme vocabulary loaded ({len(self.id_to_phoneme)} phonemes)")

        except Exception as e:
            print(f"Warning: Could not load phoneme vocabulary: {e}", file=sys.stderr)
            self.id_to_phoneme = {}

    def _decode_phonemes(self, predicted_ids):
        """Decode predicted IDs to phoneme string with timing-based spacing."""
        if not self.id_to_phoneme:
            return ""

        phonemes = []
        frame_gaps = []

        prev_id = None
        prev_frame = 0

        for frame_idx, token_id in enumerate(predicted_ids[0].tolist()):
            if token_id in self.id_to_phoneme:
                phoneme = self.id_to_phoneme[token_id]

                if phoneme not in ['<pad>', '<s>', '</s>', '<unk>']:
                    if token_id != prev_id and prev_id is not None:
                        gap = frame_idx - prev_frame
                        frame_gaps.append(gap)
                        phonemes.append(phoneme)
                        prev_frame = frame_idx
                    elif prev_id is None:
                        phonemes.append(phoneme)
                        prev_frame = frame_idx

                    prev_id = token_id

        if not phonemes or len(frame_gaps) == 0:
            return ''.join(phonemes) if phonemes else ""

        # Calculate word-boundary percentile thresholds
        gaps_sorted = sorted(frame_gaps)
        percentiles = [0.60, 0.75, 0.90]
        thresholds = []

        for p in percentiles:
            idx = min(int(len(gaps_sorted) * p), len(gaps_sorted) - 1)
            thresholds.append(gaps_sorted[idx])

        # Build output with graduated spacing
        result = [phonemes[0]]
        for i, gap in enumerate(frame_gaps):
            spaces = sum(1 for threshold in thresholds if gap > threshold)
            result.append(' ' * spaces)
            result.append(phonemes[i + 1])

        return ''.join(result)

    def _transcribe_audio(self, audio_data: np.ndarray) -> str:
        """Transcribe audio using Wav2Vec2 phoneme recognition."""
        return self._process_audio(audio_data)

    def _process_audio_at_speed(self, audio_data: np.ndarray, speed_factor: float) -> str:
        """Process audio at a specific speed and return raw phonemes."""
        try:
            # Apply time stretching if not 1.0
            if speed_factor != 1.0:
                stretched_audio = pyrb.time_stretch(audio_data, self.config.sample_rate, speed_factor)
            else:
                stretched_audio = audio_data

            # Process with Wav2Vec2
            with torch.no_grad():
                input_values = self.feature_extractor(
                    stretched_audio,
                    sampling_rate=self.config.sample_rate,
                    return_tensors="pt"
                ).input_values

                logits = self.model(input_values).logits
                predicted_ids = torch.argmax(logits, dim=-1)
                raw_phonemes = self._decode_phonemes(predicted_ids)

                return raw_phonemes

        except Exception as e:
            print(f"Error processing audio at speed {speed_factor}: {e}", file=sys.stderr)
            return ""

    def _process_audio(self, audio_data: np.ndarray) -> str:
        """Process complete audio data with Wav2Vec2 at multiple speeds."""
        try:
            if len(audio_data) == 0:
                return ""

            audio_data = self.normalize_to_float32(audio_data)
            audio_data = self.squeeze_to_mono(audio_data)

            if not self.validate_audio_length(audio_data, self.config.sample_rate):
                print(f"Audio too short for Wav2Vec2", file=sys.stderr)
                return ""

            # Process at multiple speeds in parallel threads
            results = []
            seen_phonemes = set()
            speed_results = {}

            with ThreadPoolExecutor(max_workers=len(self.speed_factors)) as executor:
                future_to_speed = {
                    executor.submit(self._process_audio_at_speed, audio_data, speed): speed
                    for speed in self.speed_factors
                }

                for future in as_completed(future_to_speed):
                    speed_factor = future_to_speed[future]
                    try:
                        raw_phonemes = future.result()
                        speed_results[speed_factor] = raw_phonemes
                    except Exception as e:
                        print(f"Error processing speed {speed_factor}: {e}", file=sys.stderr)
                        speed_results[speed_factor] = ""

            for speed_factor in self.speed_factors:
                raw_phonemes = speed_results.get(speed_factor, "")
                if raw_phonemes:
                    if raw_phonemes not in seen_phonemes:
                        seen_phonemes.add(raw_phonemes)
                        speed_pct = int(speed_factor * 100)
                        results.append(f"  {speed_pct}% speed:\n    IPA: {raw_phonemes}")
                        print(f"{speed_pct}% speed - IPA: {raw_phonemes}")
                    else:
                        speed_pct = int(speed_factor * 100)
                        print(f"{speed_pct}% speed - Skipped (duplicate of previous speed)")

            # Combine all results
            if results:
                return "\n\n".join(results)
            else:
                return ""

        except Exception as e:
            print(f"Error processing audio with Wav2Vec2: {e}", file=sys.stderr)
            return ""

    def initialize(self) -> bool:
        """Initialize HuggingFace Wav2Vec2 audio source."""
        try:
            if torch is None or transformers is None:
                print("Error: PyTorch and transformers libraries not available", file=sys.stderr)
                return False

            if not super().initialize():
                return False

            print(f"HuggingFace Wav2Vec2 initialized with model: {self.model_identifier}")
            return True

        except Exception as e:
            print(f"Error initializing HuggingFace audio source: {e}", file=sys.stderr)
            return False
