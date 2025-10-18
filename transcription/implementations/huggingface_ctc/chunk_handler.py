"""HuggingFace CTC chunk handler for real-time transcription."""

import os
import numpy as np

try:
    import torch
    import transformers
    from transformers import (
        AutoModelForCTC,
        AutoProcessor
    )
    from transformers.utils import is_offline_mode
    from huggingface_hub import HfApi
except ImportError:
    torch = None
    transformers = None
    AutoModelForCTC = None
    AutoProcessor = None
    is_offline_mode = None
    HfApi = None

from audio_source import AudioChunkHandler
from lib.pr_log import pr_err, pr_warn, pr_info
from .processor_loading import load_processor_with_fallback, is_phoneme_tokenizer, format_ctc_output


class CTCChunkHandler(AudioChunkHandler):
    """Handles real-time transcription using CTC models."""

    def __init__(self, model_path: str, sample_rate: int):
        if torch is None or transformers is None:
            raise ImportError("PyTorch and transformers libraries not installed. Install with: pip install torch transformers huggingface_hub")

        self.sample_rate = sample_rate
        self.model_path = model_path

        try:
            pr_info(f"Loading CTC model: {model_path}")

            is_local_path = os.path.exists(model_path)
            offline_mode = is_offline_mode() if is_offline_mode else False

            if not is_local_path and not offline_mode:
                pr_info("Downloading from Hugging Face (this may take a moment)...")
                try:
                    if HfApi:
                        api = HfApi()
                        api.model_info(model_path)
                except Exception as hf_error:
                    pr_warn(f"Could not verify model on Hugging Face: {hf_error}")

            self.processor = load_processor_with_fallback(
                model_path,
                cache_dir=None,
                force_download=False,
                local_files_only=offline_mode
            )

            self.model = AutoModelForCTC.from_pretrained(
                model_path,
                cache_dir=None,
                force_download=False,
                local_files_only=offline_mode
            )
            output_type = "phoneme" if is_phoneme_tokenizer(self.processor) else "character"
            pr_info(f"Loaded as CTC model ({output_type} output)")
            self.model.eval()
            pr_info(f"Successfully loaded CTC model: {model_path}")

            if hasattr(self.model.config, 'vocab_size'):
                pr_info(f"Model vocab size: {self.model.config.vocab_size}")

        except RuntimeError as e:
            if "has no tokenizer" in str(e):
                raise RuntimeError(str(e)) from None
            raise
        except Exception as e:
            error_msg = f"Failed to load CTC model from {model_path}: {e}\n"
            if is_local_path:
                error_msg += "Local path exists but model loading failed. Check if it's a valid CTC model."
            else:
                error_msg += "Make sure the model exists on Hugging Face or provide a valid local path.\n"
                error_msg += "Supported models: Wav2Vec2, HuBERT, Wav2Vec2-Conformer, Data2Vec"
            raise RuntimeError(error_msg) from None

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
            if chunk.size == 0 or len(chunk) < 10:
                return

            if chunk.dtype != np.float32:
                chunk = chunk.astype(np.float32) / 32768.0

            self.accumulated_audio.append(chunk)

        except Exception as e:
            pr_err(f"Error processing audio chunk in CTC model: {e}")

    def finalize(self) -> str:
        """Get final phoneme transcription result."""
        try:
            if not self.accumulated_audio:
                self.is_complete = True
                return ""

            full_audio = np.concatenate(self.accumulated_audio)

            min_samples = max(320, self.sample_rate // 50)
            if len(full_audio) < min_samples:
                pr_warn(f"Audio too short for CTC model: {len(full_audio)} samples, need at least {min_samples}")
                self.is_complete = True
                return ""

            with torch.no_grad():
                input_values = self.processor(
                    full_audio,
                    sampling_rate=self.sample_rate,
                    return_tensors="pt"
                ).input_values

                logits = self.model(input_values).logits
                predicted_ids = torch.argmax(logits, dim=-1)

                raw_output = self.processor.batch_decode(predicted_ids)[0]
                self.phoneme_text = format_ctc_output(raw_output, self.processor)

            self.is_complete = True
            return self.phoneme_text.strip()

        except Exception as e:
            pr_err(f"Error finalizing CTC transcription: {e}")
            self.is_complete = True
            return ""
