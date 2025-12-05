"""Test tokenizer loading for phoneme models."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from transcription.implementations.huggingface import load_processor_with_fallback


def test_phoneme_model_tokenizer():
    """Test that phoneme model loads correct tokenizer."""
    processor = load_processor_with_fallback('facebook/wav2vec2-lv-60-espeak-cv-ft')

    print(f"Processor type: {type(processor)}")
    print(f"Tokenizer type: {type(processor.tokenizer)}")
    print(f"Tokenizer class: {processor.tokenizer.__class__.__name__}")
    print(f"Is bool: {isinstance(processor.tokenizer, bool)}")

    assert not isinstance(processor.tokenizer, bool), "Tokenizer should not be bool"
    assert hasattr(processor.tokenizer, 'batch_decode'), "Tokenizer must have batch_decode"


if __name__ == '__main__':
    test_phoneme_model_tokenizer()
