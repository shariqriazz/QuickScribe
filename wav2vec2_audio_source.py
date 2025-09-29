"""Wav2Vec2-based audio source implementation for QuickScribe."""

import os
import sys
import numpy as np
from typing import Optional

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

from audio_source import AudioChunkHandler, AudioResult, AudioTextResult, AudioDataResult
from microphone_audio_source import MicrophoneAudioSource
from phoneme_mapper import process_wav2vec2_output


def format_phoneme_output(raw_phonemes: str) -> str:
    """Format phoneme output showing both IPA and alphanumeric versions."""
    alpha_phonemes = process_wav2vec2_output(raw_phonemes)
    return f"\n    IPA: {raw_phonemes.strip()}\n  ALPHA: {alpha_phonemes.strip()}"


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


class Wav2Vec2AudioSource(MicrophoneAudioSource):
    """Audio source that performs phoneme recognition using Wav2Vec2 on complete audio."""

    def __init__(self, config, model_path: str, dtype: str = 'float32'):
        # Initialize parent without chunk handler for now
        super().__init__(config, dtype)

        self.model_path = model_path
        self.sample_rate = config.sample_rate

        # Load Wav2Vec2 model components
        self._load_model(model_path)

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
        """Decode predicted IDs to phoneme string."""
        if not self.id_to_phoneme:
            return ""

        phonemes = []
        for token_id in predicted_ids[0].tolist():  # Take first batch
            if token_id in self.id_to_phoneme:
                phoneme = self.id_to_phoneme[token_id]
                # Skip special tokens
                if phoneme not in ['<pad>', '<s>', '</s>', '<unk>']:
                    phonemes.append(phoneme)

        return ' '.join(phonemes)

    def get_result(self) -> AudioResult:
        """Override to process complete audio with Wav2Vec2."""
        result = super().get_result()

        if isinstance(result, AudioDataResult):
            # Process the complete audio data with Wav2Vec2
            phoneme_text = self._process_audio(result.audio_data)
            return AudioDataResult(result.audio_data, phoneme_text)

        return result

    def _process_audio(self, audio_data: np.ndarray) -> str:
        """Process complete audio data with Wav2Vec2."""
        try:
            if len(audio_data) == 0:
                return ""

            # Convert to float32 if needed
            if audio_data.dtype != np.float32:
                audio_data = audio_data.astype(np.float32) / 32768.0

            # Ensure 1D array - squeeze out channel dimension if present
            if audio_data.ndim > 1:
                audio_data = np.squeeze(audio_data)

            # Check minimum length
            min_samples = max(320, self.sample_rate // 50)  # At least 20ms of audio
            if len(audio_data) < min_samples:
                print(f"Audio too short for Wav2Vec2: {len(audio_data)} samples (need {min_samples})", file=sys.stderr)
                return ""

            # Process with Wav2Vec2
            with torch.no_grad():
                input_values = self.feature_extractor(
                    audio_data,
                    sampling_rate=self.sample_rate,
                    return_tensors="pt"
                ).input_values

                logits = self.model(input_values).logits
                predicted_ids = torch.argmax(logits, dim=-1)
                raw_phonemes = self._decode_phonemes(predicted_ids)

                # Show before and after mapping
                alpha_phonemes = process_wav2vec2_output(raw_phonemes)
                print(f"Raw IPA phonemes: {raw_phonemes}")
                print(f"Mapped alphanumeric: {alpha_phonemes}")

                # Return formatted output with both IPA and alphanumeric
                return format_phoneme_output(raw_phonemes)

        except Exception as e:
            print(f"Error processing audio with Wav2Vec2: {e}", file=sys.stderr)
            return ""

    def stop_recording(self) -> AudioResult:
        """Override to process audio with Wav2Vec2 and return AudioTextResult."""
        # Get the raw audio data from parent
        audio_result = super().stop_recording()

        if isinstance(audio_result, AudioDataResult):
            # Process the audio data with Wav2Vec2
            phoneme_text = self._process_audio(audio_result.audio_data)

            if phoneme_text:
                print(f"Wav2Vec2 phonemes: {phoneme_text}")

            # Return AudioTextResult with phoneme text
            return AudioTextResult(
                transcribed_text=phoneme_text,
                sample_rate=audio_result.sample_rate,
                audio_data=audio_result.audio_data
            )

        return audio_result
