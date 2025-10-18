"""HuggingFace CTC transcription audio source implementation."""

import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    import torch
    import transformers
    from transformers import (
        AutoModelForCTC,
        AutoProcessor
    )
    from transformers.utils import is_offline_mode
except ImportError:
    torch = None
    transformers = None
    AutoModelForCTC = None
    AutoProcessor = None
    is_offline_mode = None

try:
    import pyrubberband as pyrb
except ImportError:
    pyrb = None

from transcription.base import TranscriptionAudioSource, parse_transcription_model
from lib.pr_log import pr_err, pr_warn, pr_info
from .processor_loading import load_processor_with_fallback, is_phoneme_tokenizer


class HuggingFaceCTCTranscriptionAudioSource(TranscriptionAudioSource):
    """HuggingFace CTC transcription implementation."""

    def __init__(self, config, transcription_model: str):
        model_identifier = parse_transcription_model(transcription_model)
        super().__init__(config, model_identifier, supports_streaming=False, dtype='float32')

        self.speed_factors = [0.80, 0.85, 0.90, 0.95]

        if pyrb is None:
            raise ImportError("pyrubberband library not installed. Install with: pip install pyrubberband")

        self._load_model(model_identifier)

    def _load_model(self, model_path: str):
        """Load CTC model and processor."""
        if torch is None or transformers is None:
            raise ImportError("PyTorch and transformers libraries not installed. Install with: pip install torch transformers huggingface_hub")

        try:
            pr_info(f"Loading CTC model: {model_path}")

            offline_mode = is_offline_mode() if is_offline_mode else False

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

            self.model.eval()
            pr_info(f"Successfully loaded CTC model: {model_path}")

        except RuntimeError as e:
            if "has no tokenizer" in str(e):
                raise RuntimeError(str(e)) from None
            raise RuntimeError(f"Failed to load CTC model from {model_path}: {e}") from None
        except Exception as e:
            raise RuntimeError(f"Failed to load CTC model from {model_path}: {e}") from None

    def _transcribe_audio(self, audio_data: np.ndarray) -> str:
        """Transcribe audio using CTC phoneme recognition."""
        return self._process_audio(audio_data)

    def _process_audio_at_speed(self, audio_data: np.ndarray, speed_factor: float) -> str:
        """Process audio at a specific speed and return raw phonemes."""
        try:
            if speed_factor != 1.0:
                stretched_audio = pyrb.time_stretch(audio_data, self.config.sample_rate, speed_factor)
            else:
                stretched_audio = audio_data

            with torch.no_grad():
                input_values = self.processor(
                    stretched_audio,
                    sampling_rate=self.config.sample_rate,
                    return_tensors="pt"
                ).input_values

                logits = self.model(input_values).logits
                predicted_ids = torch.argmax(logits, dim=-1)
                raw_output = self.processor.batch_decode(predicted_ids)[0]

                return raw_output

        except Exception as e:
            pr_err(f"Error processing audio at speed {speed_factor}: {e}")
            return ""

    def _process_audio(self, audio_data: np.ndarray) -> str:
        """Process complete audio data with CTC model at multiple speeds."""
        try:
            if len(audio_data) == 0:
                return ""

            audio_data = self.normalize_to_float32(audio_data)
            audio_data = self.squeeze_to_mono(audio_data)

            if not self.validate_audio_length(audio_data, self.config.sample_rate):
                pr_warn(f"Audio too short for CTC model")
                return ""

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
                        pr_err(f"Error processing speed {speed_factor}: {e}")
                        speed_results[speed_factor] = ""

            prefix = "IPA" if is_phoneme_tokenizer(self.processor) else "Text"
            for speed_factor in self.speed_factors:
                raw_output = speed_results.get(speed_factor, "")
                if raw_output:
                    if raw_output not in seen_phonemes:
                        seen_phonemes.add(raw_output)
                        speed_pct = int(speed_factor * 100)
                        results.append(f"  {speed_pct}% speed:\n    {prefix}: {raw_output}")
                        pr_info(f"{speed_pct}% speed - {prefix}: {raw_output}")
                    else:
                        speed_pct = int(speed_factor * 100)
                        pr_info(f"{speed_pct}% speed - Skipped (duplicate of previous speed)")

            if results:
                return "\n\n".join(results)
            else:
                return ""

        except Exception as e:
            pr_err(f"Error processing audio with CTC model: {e}")
            return ""

    def initialize(self) -> bool:
        """Initialize HuggingFace CTC audio source."""
        try:
            if torch is None or transformers is None:
                pr_err("PyTorch and transformers libraries not available")
                return False

            if not super().initialize():
                return False

            pr_info(f"HuggingFace CTC initialized with model: {self.model_identifier}")
            return True

        except Exception as e:
            pr_err(f"Error initializing HuggingFace audio source: {e}")
            return False
