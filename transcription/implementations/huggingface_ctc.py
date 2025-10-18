"""HuggingFace CTC-based transcription implementation for QuickScribe."""

import os
import sys
import numpy as np
from typing import Optional
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    import torch
    import transformers
    from transformers import (
        AutoModelForCTC,
        AutoProcessor,
        AutoFeatureExtractor,
        AutoTokenizer,
        Wav2Vec2CTCTokenizer,
        Wav2Vec2PhonemeCTCTokenizer
    )
    from transformers.utils import is_offline_mode
    from huggingface_hub import HfApi
except ImportError:
    torch = None
    transformers = None
    AutoModelForCTC = None
    AutoProcessor = None
    AutoFeatureExtractor = None
    AutoTokenizer = None
    Wav2Vec2CTCTokenizer = None
    Wav2Vec2PhonemeCTCTokenizer = None
    is_offline_mode = None
    HfApi = None

try:
    import pyrubberband as pyrb
except ImportError:
    pyrb = None

from audio_source import AudioChunkHandler, AudioResult, AudioTextResult, AudioDataResult
from transcription.base import TranscriptionAudioSource, parse_transcription_model
from phoneme_mapper import process_wav2vec2_output
from lib.pr_log import pr_err, pr_warn, pr_info


class SimpleTokenizerWrapper:
    """Minimal tokenizer wrapper for vocab-based decoding."""

    def __init__(self, vocab_dict):
        self.vocab = vocab_dict
        self.id_to_token = {int(idx): token for token, idx in vocab_dict.items()}

    def batch_decode(self, token_ids, **kwargs):
        """Decode token IDs to text."""
        results = []
        for sequence in token_ids:
            tokens = []
            prev_id = None
            for token_id in sequence.tolist() if hasattr(sequence, 'tolist') else sequence:
                if token_id != prev_id and token_id in self.id_to_token:
                    token = self.id_to_token[token_id]
                    if token not in ['<pad>', '<s>', '</s>', '<unk>']:
                        tokens.append(token)
                prev_id = token_id
            results.append(' '.join(tokens))
        return results


class ProcessorWrapper:
    """Wrapper combining feature extractor and tokenizer when AutoProcessor fails."""

    def __init__(self, feature_extractor, tokenizer):
        self.feature_extractor = feature_extractor
        self.tokenizer = tokenizer

    def __call__(self, *args, **kwargs):
        return self.feature_extractor(*args, **kwargs)

    def batch_decode(self, *args, **kwargs):
        return self.tokenizer.batch_decode(*args, **kwargs)


def load_processor_with_fallback(model_path: str, cache_dir=None, force_download=False, local_files_only=False):
    """
    Load processor with fallback to separate components if AutoProcessor fails.

    Args:
        model_path: Model identifier or path
        cache_dir: Cache directory for models
        force_download: Force re-download
        local_files_only: Only use local files

    Returns:
        Processor or ProcessorWrapper instance
    """
    try:
        return AutoProcessor.from_pretrained(
            model_path,
            cache_dir=cache_dir,
            force_download=force_download,
            local_files_only=local_files_only
        )
    except (TypeError, ValueError) as proc_error:
        pr_info(f"Loading processor components separately")

        from transformers import AutoConfig
        config = AutoConfig.from_pretrained(
            model_path,
            cache_dir=cache_dir,
            local_files_only=local_files_only
        )

        feature_extractor = AutoFeatureExtractor.from_pretrained(
            model_path,
            cache_dir=cache_dir,
            force_download=force_download,
            local_files_only=local_files_only
        )

        tokenizer = None
        try:
            from huggingface_hub import hf_hub_download
            import json

            tokenizer_config_file = hf_hub_download(
                repo_id=model_path,
                filename='tokenizer_config.json',
                cache_dir=cache_dir,
                local_files_only=local_files_only
            )
            with open(tokenizer_config_file, 'r') as f:
                tokenizer_config = json.load(f)
            tokenizer_class_name = tokenizer_config.get('tokenizer_class', '')

            if 'Phoneme' in tokenizer_class_name:
                vocab_file = hf_hub_download(
                    repo_id=model_path,
                    filename='vocab.json',
                    cache_dir=cache_dir,
                    local_files_only=local_files_only
                )
                with open(vocab_file, 'r') as f:
                    vocab_dict = json.load(f)

                tokenizer = SimpleTokenizerWrapper(vocab_dict)
                pr_info(f"Loaded tokenizer: SimpleTokenizerWrapper (phoneme vocab)")
            else:
                tokenizer = Wav2Vec2CTCTokenizer.from_pretrained(
                    model_path,
                    cache_dir=cache_dir,
                    force_download=force_download
                )
                pr_info(f"Loaded tokenizer: Wav2Vec2CTCTokenizer (from config)")
        except Exception as config_error:
            pr_warn(f"No tokenizer config found, trying direct loading: {config_error}")
            for tokenizer_class in [Wav2Vec2PhonemeCTCTokenizer, Wav2Vec2CTCTokenizer]:
                try:
                    loaded_tokenizer = tokenizer_class.from_pretrained(
                        model_path,
                        cache_dir=cache_dir,
                        force_download=force_download,
                        local_files_only=local_files_only
                    )

                    if hasattr(loaded_tokenizer, 'get_vocab'):
                        vocab = loaded_tokenizer.get_vocab()
                        if vocab and len(vocab) > 0:
                            tokenizer = loaded_tokenizer
                            pr_info(f"Loaded tokenizer: {tokenizer_class.__name__}")
                            break
                        else:
                            pr_warn(f"{tokenizer_class.__name__} loaded but has empty vocabulary")
                    else:
                        pr_warn(f"{tokenizer_class.__name__} has no get_vocab method")
                except Exception:
                    continue

        if tokenizer is None:
            raise RuntimeError(
                f"Model '{model_path}' has no tokenizer. "
                "This indicates a pretrained-only model that requires fine-tuning for ASR. "
                "Use a fine-tuned variant with included tokenizer (e.g., facebook/hubert-large-ls960-ft)."
            )

        pr_info(f"Creating ProcessorWrapper with tokenizer type: {type(tokenizer).__name__}")
        return ProcessorWrapper(feature_extractor, tokenizer)


def is_phoneme_tokenizer(processor) -> bool:
    """Detect if processor uses phoneme tokenizer."""
    tokenizer = processor.tokenizer
    tokenizer_class = type(tokenizer).__name__

    if 'Phoneme' in tokenizer_class:
        return True

    if hasattr(tokenizer, 'do_phonemize') or hasattr(tokenizer, 'phonemizer_backend'):
        return True

    return False


def format_ctc_output(raw_text: str, processor) -> str:
    """Format CTC output with appropriate label."""
    prefix = "IPA: " if is_phoneme_tokenizer(processor) else "Text: "
    return f"\n    {prefix}{raw_text.strip()}"


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
