"""HuggingFace CTC processor loading utilities."""

import os
import sys
import numpy as np
from typing import Optional

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
