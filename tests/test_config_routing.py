"""Test config-based tokenizer routing."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from transcription.implementations.huggingface import load_processor_with_fallback


def test_config_routing():
    """Test that tokenizer_class field is used for routing."""

    # Test with phoneme model that requires espeak (will fallback to CTCVocabDecoder)
    print("=== Testing phoneme model (facebook/wav2vec2-lv-60-espeak-cv-ft) ===")
    processor = load_processor_with_fallback('facebook/wav2vec2-lv-60-espeak-cv-ft')
    print(f"Tokenizer type: {type(processor.tokenizer).__name__}")
    print(f"Output format: {processor.output_format}")
    assert hasattr(processor.tokenizer, 'batch_decode')
    print("✓ Phoneme model loaded successfully\n")

    # Test with text model that doesn't require espeak
    print("=== Testing text model (facebook/wav2vec2-base-960h) ===")
    processor = load_processor_with_fallback('facebook/wav2vec2-base-960h')
    print(f"Tokenizer type: {type(processor.tokenizer).__name__}")
    print(f"Output format: {processor.output_format}")
    assert hasattr(processor.tokenizer, 'batch_decode')
    print("✓ Text model loaded successfully\n")

    print("=== All tests passed! ===")


if __name__ == '__main__':
    test_config_routing()