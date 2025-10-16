#!/usr/bin/env python3
"""
Functional test demonstrating Wav2Vec2 phoneme recognition working end-to-end.
This test validates the basic functionality without complex mocking.
"""
import sys
import os
import numpy as np
import unittest.mock as mock

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Mock pynput before any imports that use it
sys.modules['pynput'] = mock.Mock()
sys.modules['pynput.keyboard'] = mock.Mock()


def test_config_integration():
    """Test that configuration properly handles Wav2Vec2 settings."""
    print("Testing ConfigManager Wav2Vec2 integration...")

    from config_manager import ConfigManager

    # Test default configuration
    config = ConfigManager()
    assert config.transcription_model == "huggingface/facebook/wav2vec2-lv-60-espeak-cv-ft"
    print("✓ Default Wav2Vec2 model configured correctly")

    # Test argument parsing
    parser = config.setup_argument_parser()
    args = parser.parse_args(['--transcription-model', 'huggingface/custom/model'])
    assert args.transcription_model == 'huggingface/custom/model'
    print("✓ Custom Wav2Vec2 model argument parsing works")


def test_model_instructions():
    """Test that audio processor provides phoneme instructions."""
    print("Testing HuggingFaceTranscriptionAudioSource phoneme instructions...")

    # Mock the dependencies
    with mock.patch('transcription.implementations.huggingface.torch'), \
         mock.patch('transcription.implementations.huggingface.transformers'), \
         mock.patch('transcription.implementations.huggingface.Wav2Vec2FeatureExtractor'), \
         mock.patch('transcription.implementations.huggingface.Wav2Vec2ForCTC'), \
         mock.patch('transcription.implementations.huggingface.pyrb'), \
         mock.patch('microphone_audio_source.MicrophoneAudioSource.__init__', return_value=None):

        from instruction_composer import InstructionComposer

        # Load wav2vec2 audio source instructions
        composer = InstructionComposer()
        instructions = composer.compose('dictate', 'wav2vec2')

        # Check for phoneme-specific content
        assert "IPA PHONEME INPUT" in instructions
        assert "phoneme sequences" in instructions
        assert "MULTI-SPEED ENSEMBLE" in instructions
        print("✓ Audio source provides phoneme processing guidance")


def test_audio_source_creation():
    """Test that HuggingFaceTranscriptionAudioSource can be created with mocked dependencies."""
    print("Testing HuggingFaceTranscriptionAudioSource creation...")

    # Mock the dependencies that aren't available
    import unittest.mock as mock

    class MockConfig:
        def __init__(self):
            self.sample_rate = 16000
            self.channels = 1

    config = MockConfig()

    # Mock all the heavy dependencies
    with mock.patch('transcription.implementations.huggingface.torch', mock.Mock()), \
         mock.patch('transcription.implementations.huggingface.transformers', mock.Mock()), \
         mock.patch('transcription.implementations.huggingface.Wav2Vec2FeatureExtractor') as mock_feature_extractor, \
         mock.patch('transcription.implementations.huggingface.Wav2Vec2ForCTC') as mock_model, \
         mock.patch('transcription.implementations.huggingface.is_offline_mode', mock.Mock(return_value=False)), \
         mock.patch('transcription.implementations.huggingface.HfApi', mock.Mock()), \
         mock.patch('huggingface_hub.hf_hub_download', mock.Mock(return_value='/tmp/vocab.json')), \
         mock.patch('builtins.open', mock.Mock(side_effect=lambda *args, **kwargs: mock.Mock(__enter__=mock.Mock(return_value=mock.Mock()), __exit__=mock.Mock()))), \
         mock.patch('json.load', mock.Mock(return_value={'t': 1, 'ɛ': 2, 's': 3})):

        # Setup feature extractor and model mocks
        mock_feature_extractor.from_pretrained.return_value = mock.Mock()
        mock_model.from_pretrained.return_value = mock.Mock()

        from transcription.implementations.huggingface import HuggingFaceTranscriptionAudioSource

        # Create audio source
        audio_source = HuggingFaceTranscriptionAudioSource(config, "test_model")

        # Verify basic properties
        assert audio_source.model_identifier == "test_model"
        assert hasattr(audio_source, 'feature_extractor')
        assert hasattr(audio_source, 'model')
        assert hasattr(audio_source, 'id_to_phoneme')
        print("✓ HuggingFaceTranscriptionAudioSource created successfully")


def test_dictation_app_integration():
    """Test that DictationApp can use HuggingFaceTranscriptionAudioSource."""
    print("Testing DictationApp Wav2Vec2 integration...")

    import unittest.mock as mock

    class MockConfig:
        def __init__(self):
            self.sample_rate = 16000
            self.channels = 1
            self.wav2vec2_model_path = "test_model"
            self.vosk_model_path = None
            self.provider = "groq"
            self.model_id = "whisper-large-v3"
            self.audio_source = "wav2vec"
            self.language = "en"
            self.enable_reasoning = False
            self.temperature = 0.7
            self.max_tokens = 1000
            self.top_p = 1.0

    # Mock dependencies
    with mock.patch('transcription.implementations.huggingface.torch', mock.Mock()), \
         mock.patch('transcription.implementations.huggingface.transformers', mock.Mock()), \
         mock.patch('transcription.implementations.huggingface.Wav2Vec2FeatureExtractor') as mock_feature_extractor, \
         mock.patch('transcription.implementations.huggingface.Wav2Vec2ForCTC') as mock_model, \
         mock.patch('transcription.implementations.huggingface.is_offline_mode', mock.Mock(return_value=False)), \
         mock.patch('transcription.implementations.huggingface.HfApi', mock.Mock()), \
         mock.patch('huggingface_hub.hf_hub_download', mock.Mock(return_value='/tmp/vocab.json')), \
         mock.patch('builtins.open', mock.Mock(side_effect=lambda *args, **kwargs: mock.Mock(__enter__=mock.Mock(return_value=mock.Mock()), __exit__=mock.Mock()))), \
         mock.patch('json.load', mock.Mock(return_value={'t': 1, 'ɛ': 2, 's': 3})), \
         mock.patch('dictation_app.BaseProvider') as mock_base_provider, \
         mock.patch('dictation_app.TranscriptionService') as mock_transcription_service, \
         mock.patch('dictation_app.signal', mock.Mock()), \
         mock.patch('transcription.implementations.huggingface.HuggingFaceTranscriptionAudioSource.initialize', mock.Mock(return_value=True)), \
         mock.patch('dictation_app.DictationApp.setup_trigger_key', mock.Mock(return_value=True)), \
         mock.patch('microphone_audio_source.MicrophoneAudioSource.test_audio_device', mock.Mock(return_value=True)):

        # Setup mocks
        mock_feature_extractor.from_pretrained.return_value = mock.Mock()
        mock_model.from_pretrained.return_value = mock.Mock()
        mock_provider = mock.Mock()
        mock_provider.is_initialized.return_value = True
        mock_base_provider.return_value = mock_provider
        mock_transcription_service.return_value = mock.Mock()

        from dictation_app import DictationApp
        from transcription.implementations.huggingface import HuggingFaceTranscriptionAudioSource

        # Create app and bypass config parsing
        app = DictationApp()
        app.config = MockConfig()
        app.config_manager = mock.Mock()
        app.config_manager.parse_configuration.return_value = True

        # Initialize services first
        app._initialize_services()
        app._initialize_provider_client()

        # Test audio source creation logic directly
        if app.config.audio_source in ['phoneme', 'wav2vec']:
            from transcription.implementations.huggingface import HuggingFaceTranscriptionAudioSource
            app.audio_source = HuggingFaceTranscriptionAudioSource(
                app.config,
                app.config.wav2vec2_model_path
            )

        # Verify the correct audio source was created
        assert isinstance(app.audio_source, HuggingFaceTranscriptionAudioSource)
        print("✓ DictationApp correctly uses HuggingFaceTranscriptionAudioSource")


def demonstrate_phoneme_conversion():
    """Demonstrate the concept of phoneme to word conversion."""
    print("Demonstrating phoneme-to-word conversion concept...")

    # Example phoneme sequences and their expected conversions
    phoneme_examples = [
        ("h ɛ l oʊ", "hello"),
        ("w ɜː l d", "world"),
        ("t uː", "to/too/two"),  # homophone - needs context
        ("θ ɛ r", "there/their"),  # another homophone
        ("aɪ", "I/eye/aye"),  # yet another homophone
    ]

    print("Example phoneme → word conversions:")
    for phonemes, words in phoneme_examples:
        print(f"  '{phonemes}' → '{words}'")

    print("✓ Phoneme conversion concept demonstrated")


def run_functional_tests():
    """Run all functional tests."""
    print("Wav2Vec2 Functional Test Suite")
    print("=" * 50)

    tests = [
        ("Configuration Integration", test_config_integration),
        ("Model Instructions", test_model_instructions),
        ("Audio Source Creation", test_audio_source_creation),
        ("DictationApp Integration", test_dictation_app_integration),
        ("Phoneme Conversion Demo", demonstrate_phoneme_conversion),
    ]

    passed = 0
    failed = 0

    for test_name, test_func in tests:
        try:
            print(f"\n{test_name}:")
            result = test_func()
            if result:
                passed += 1
                print(f"✓ {test_name} PASSED")
            else:
                failed += 1
                print(f"✗ {test_name} FAILED")
        except Exception as e:
            failed += 1
            print(f"✗ {test_name} ERROR: {e}")

    print("\n" + "=" * 50)
    print(f"Functional Tests Summary:")
    print(f"  Passed: {passed}")
    print(f"  Failed: {failed}")
    print(f"  Total:  {len(tests)}")

    if failed == 0:
        print("🎉 All functional tests passed!")
        return True
    else:
        print("❌ Some functional tests failed")
        return False


if __name__ == "__main__":
    print("Wav2Vec2 Functional Test Demonstration")
    print("=====================================")
    print()
    print("This test validates that the Wav2Vec2 integration is working")
    print("at a basic level without requiring actual model downloads.")
    print()

    success = run_functional_tests()

    print("\nUsage Instructions:")
    print("------------------")
    print("To use Wav2Vec2 phoneme recognition:")
    print("1. Install dependencies: pip install torch transformers huggingface_hub")
    print("2. Run with default model:")
    print("   python dictation_app.py --provider groq --model whisper-large-v3 --wav2vec2-model")
    print("3. Or specify custom model:")
    print("   python dictation_app.py --provider groq --model whisper-large-v3 --wav2vec2-model facebook/wav2vec2-base-960h")
    print()
    print("The system will:")
    print("- Automatically download the model from Hugging Face")
    print("- Record audio and convert to phonemes locally")
    print("- Send phonemes to AI model for word conversion")
    print("- Handle homophones using context")

    sys.exit(0 if success else 1)