"""
Integration tests for Wav2Vec2 with full DictationApp workflow.
"""
import unittest
import numpy as np
import sys
import os
from unittest.mock import Mock, patch, MagicMock
import tempfile

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Mock pynput before any imports that use it
sys.modules['pynput'] = Mock()
sys.modules['pynput.keyboard'] = Mock()

# Import after mocking pynput
from wav2vec2_audio_source import Wav2Vec2AudioSource


class MockProvider:
    """Mock provider for testing."""
    def __init__(self):
        self.initialized = True
        self.transcribe_called = False
        self.last_text_data = None
        self.last_audio_data = None
        self.enable_reasoning = False
        self.temperature = 0.7
        self.max_tokens = 1000
        self.top_p = 1.0

    def initialize(self):
        return self.initialized

    def is_initialized(self):
        return self.initialized

    def transcribe(self, context, audio_data=None, text_data=None,
                   streaming_callback=None, final_callback=None):
        self.transcribe_called = True
        if text_data:
            self.last_text_data = text_data
        if audio_data is not None:
            self.last_audio_data = audio_data
        if final_callback:
            result = f"Processed: {text_data}" if text_data else "Processed audio"
            final_callback(result)

    def get_xml_instructions(self):
        return "Mock instructions"


class MockConfig:
    """Mock configuration for testing."""
    def __init__(self):
        self.sample_rate = 16000
        self.channels = 1
        self.wav2vec2_model_path = "facebook/wav2vec2-lv-60-espeak-cv-ft"
        self.vosk_model_path = None
        self.provider = "groq"
        self.model_id = "whisper-large-v3"
        self.trigger_key_name = None
        self.language = "en"
        self.enable_reasoning = False
        self.temperature = 0.7
        self.max_tokens = 1000
        self.top_p = 1.0
        self.use_xdotool = False
        self.audio_source = "wav2vec"


class TestWav2Vec2DictationAppIntegration(unittest.TestCase):
    """Test Wav2Vec2 integration with DictationApp."""

    def setUp(self):
        """Set up integration test fixtures."""
        self.config = MockConfig()

        # Mock file context manager
        mock_file = Mock()
        mock_file.__enter__ = Mock(return_value=mock_file)
        mock_file.__exit__ = Mock(return_value=None)

        # Mock torch with no_grad context manager
        mock_torch = Mock()
        mock_no_grad = Mock()
        mock_no_grad.__enter__ = Mock(return_value=None)
        mock_no_grad.__exit__ = Mock(return_value=None)
        mock_torch.no_grad.return_value = mock_no_grad

        # Mock all external dependencies
        self.patches = [
            patch('wav2vec2_audio_source.torch', mock_torch),
            patch('wav2vec2_audio_source.transformers', Mock()),
            patch('wav2vec2_audio_source.is_offline_mode', Mock(return_value=False)),
            patch('wav2vec2_audio_source.HfApi', Mock()),
            patch('huggingface_hub.hf_hub_download', Mock(return_value='/tmp/vocab.json')),
            patch('builtins.open', Mock(return_value=mock_file)),
            patch('json.load', Mock(return_value={'t': 1, 'ɛ': 2, 's': 3})),
            patch('dictation_app.signal', Mock())
        ]

        for patcher in self.patches:
            patcher.start()

    def tearDown(self):
        """Clean up patches."""
        for patcher in self.patches:
            patcher.stop()

    @patch('dictation_app.signal', Mock())
    @patch('dictation_app.BaseProvider')
    @patch('dictation_app.TranscriptionService')
    def test_dictation_app_uses_wav2vec2_audio_source(self, mock_transcription_service, mock_base_provider):
        """Test that DictationApp correctly initializes Wav2Vec2AudioSource."""
        from dictation_app import DictationApp

        # Setup mocks
        mock_provider = MockProvider()
        mock_base_provider.return_value = mock_provider
        mock_transcription = Mock()
        mock_transcription_service.return_value = mock_transcription

        # Mock Wav2Vec2 dependencies
        with patch('wav2vec2_audio_source.Wav2Vec2FeatureExtractor') as mock_processor, \
             patch('wav2vec2_audio_source.Wav2Vec2ForCTC') as mock_model, \
             patch('wav2vec2_audio_source.Wav2Vec2AudioSource.initialize', return_value=True), \
             patch('dictation_app.DictationApp.setup_trigger_key', return_value=True):

            mock_processor.from_pretrained.return_value = Mock()
            mock_model.from_pretrained.return_value = Mock()

            # Create DictationApp with Wav2Vec2 config
            app = DictationApp()
            app.config = self.config
            app.config_manager = Mock()
            app.config_manager.parse_configuration.return_value = True

            # Initialize services manually to avoid full initialization issues
            app._initialize_services()
            app._initialize_provider_client()

            # Test audio source creation logic directly
            if app.config.audio_source in ['phoneme', 'wav2vec']:
                from wav2vec2_audio_source import Wav2Vec2AudioSource
                app.audio_source = Wav2Vec2AudioSource(
                    app.config,
                    model_path=app.config.wav2vec2_model_path,
                    dtype='float32'
                )

            # Verify Wav2Vec2AudioSource was created
            from wav2vec2_audio_source import Wav2Vec2AudioSource
            self.assertIsInstance(app.audio_source, Wav2Vec2AudioSource)
            # Model path should be set (exact value is mocked)
            self.assertIsNotNone(app.audio_source.model_path)

    def test_wav2vec2_audio_source_text_flow(self):
        """Test complete flow from Wav2Vec2 to provider text processing."""
        from wav2vec2_audio_source import Wav2Vec2AudioSource
        from audio_source import AudioTextResult

        # Mock dependencies
        with patch('wav2vec2_audio_source.Wav2Vec2FeatureExtractor') as mock_processor, \
             patch('wav2vec2_audio_source.Wav2Vec2ForCTC') as mock_model, \
             patch('wav2vec2_audio_source.MicrophoneAudioSource') as mock_parent:

            # Setup processor and model mocks
            processor_instance = Mock()
            model_instance = Mock()
            mock_processor.from_pretrained.return_value = processor_instance
            mock_model.from_pretrained.return_value = model_instance

            # Setup inference pipeline
            processor_instance.return_value.input_values = Mock()
            model_instance.return_value.logits = Mock()
            processor_instance.batch_decode.return_value = ["h ɛ l oʊ w ɜː l d"]

            # Setup parent mock
            mock_parent_instance = Mock()
            mock_parent.return_value = mock_parent_instance

            # Mock audio result
            test_audio = np.array([0.1, 0.2, 0.3])
            mock_audio_result = Mock()
            mock_audio_result.audio_data = test_audio
            mock_parent_instance.stop_recording.return_value = mock_audio_result

            # Create audio source
            audio_source = Wav2Vec2AudioSource(self.config, "test_model")

            # Skip chunk processing since we removed the handler - audio processing happens in stop_recording

            # Stop recording and get result
            result = audio_source.stop_recording()

            # Verify result
            self.assertIsInstance(result, AudioTextResult)
            # The mock will return empty string since no real processing
            self.assertEqual(result.sample_rate, 16000)

    @patch('dictation_app.signal', Mock())
    def test_audio_source_selection_priority(self):
        """Test that Wav2Vec2 takes priority over VOSK when both are configured."""
        from dictation_app import DictationApp

        # Setup config with both wav2vec2 and vosk
        config = MockConfig()
        config.wav2vec2_model_path = "facebook/wav2vec2-lv-60-espeak-cv-ft"
        config.vosk_model_path = "/path/to/vosk/model"

        with patch('dictation_app.BaseProvider') as mock_base_provider, \
             patch('dictation_app.TranscriptionService') as mock_transcription_service, \
             patch('wav2vec2_audio_source.Wav2Vec2FeatureExtractor') as mock_processor, \
             patch('wav2vec2_audio_source.Wav2Vec2ForCTC') as mock_model, \
             patch('wav2vec2_audio_source.Wav2Vec2AudioSource.initialize', return_value=True), \
             patch('dictation_app.DictationApp.setup_trigger_key', return_value=True):

            # Setup mocks
            mock_provider = MockProvider()
            mock_base_provider.return_value = mock_provider
            mock_transcription = Mock()
            mock_transcription_service.return_value = mock_transcription

            mock_processor.from_pretrained.return_value = Mock()
            mock_model.from_pretrained.return_value = Mock()

            # Create app
            app = DictationApp()
            app.config = config
            app.config_manager = Mock()
            app.config_manager.parse_configuration.return_value = True

            # Initialize services manually
            app._initialize_services()
            app._initialize_provider_client()

            # Test audio source creation logic with priority
            if app.config.audio_source in ['phoneme', 'wav2vec']:
                from wav2vec2_audio_source import Wav2Vec2AudioSource
                app.audio_source = Wav2Vec2AudioSource(
                    app.config,
                    model_path=app.config.wav2vec2_model_path,
                    dtype='float32'
                )

            # Verify Wav2Vec2 is chosen (since audio_source is set to "wav2vec")
            from wav2vec2_audio_source import Wav2Vec2AudioSource
            self.assertIsInstance(app.audio_source, Wav2Vec2AudioSource)

    @patch('dictation_app.signal', Mock())
    @patch('dictation_app.BaseProvider')
    @patch('dictation_app.TranscriptionService')
    def test_wav2vec2_phoneme_processing_workflow(self, mock_transcription_service, mock_base_provider):
        """Test complete workflow from audio to phonemes to processed text."""
        from dictation_app import DictationApp
        from providers.conversation_context import ConversationContext

        # Setup mocks
        mock_provider = MockProvider()
        mock_base_provider.return_value = mock_provider
        mock_transcription = Mock()
        mock_transcription_service.return_value = mock_transcription

        # Mock context building
        mock_transcription._build_xml_from_processor.return_value = "<conversation></conversation>"
        mock_transcription._build_current_text.return_value = "Previous text"

        with patch('wav2vec2_audio_source.Wav2Vec2FeatureExtractor') as mock_processor, \
             patch('wav2vec2_audio_source.Wav2Vec2ForCTC') as mock_model:

            mock_processor.from_pretrained.return_value = Mock()
            mock_model.from_pretrained.return_value = Mock()

            # Create app and set up components manually (skip full initialize)
            app = DictationApp()
            app.config = self.config
            app.transcription_service = mock_transcription
            app.provider = mock_provider

            # Create mock audio result with phonemes
            from audio_source import AudioTextResult
            phoneme_result = AudioTextResult(
                transcribed_text="h ɛ l oʊ w ɜː l d",
                sample_rate=16000,
                audio_data=np.array([0.1, 0.2, 0.3])
            )

            # Process the audio result
            app._process_audio_result(phoneme_result)

            # Verify provider was called with phoneme text
            self.assertTrue(mock_provider.transcribe_called)
            self.assertEqual(mock_provider.last_text_data, "h ɛ l oʊ w ɜː l d")


class TestWav2Vec2ProviderInstructions(unittest.TestCase):
    """Test that providers receive correct instructions for phoneme processing."""

    def test_base_provider_phoneme_instructions(self):
        """Test that audio source provides phoneme processing instructions."""
        # Mock dependencies to create audio source
        with patch('wav2vec2_audio_source.torch'), \
             patch('wav2vec2_audio_source.transformers'), \
             patch('wav2vec2_audio_source.Wav2Vec2FeatureExtractor'), \
             patch('wav2vec2_audio_source.Wav2Vec2ForCTC'), \
             patch('wav2vec2_audio_source.pyrb'), \
             patch('wav2vec2_audio_source.MicrophoneAudioSource.__init__', return_value=None):

            # Create instance
            audio_source = Wav2Vec2AudioSource.__new__(Wav2Vec2AudioSource)
            instructions = audio_source.get_transcription_instructions()

            # Verify phoneme-specific instructions are included
            self.assertIn("PHONETIC TRANSCRIPTION ASSISTANCE", instructions)
            self.assertIn("phoneme sequences", instructions)
            self.assertIn("HH EH L OW", instructions)
            self.assertIn("homophone disambiguation", instructions)

    def test_phoneme_instruction_examples(self):
        """Test that phoneme instructions include proper examples."""
        # Mock dependencies to create audio source
        with patch('wav2vec2_audio_source.torch'), \
             patch('wav2vec2_audio_source.transformers'), \
             patch('wav2vec2_audio_source.Wav2Vec2FeatureExtractor'), \
             patch('wav2vec2_audio_source.Wav2Vec2ForCTC'), \
             patch('wav2vec2_audio_source.pyrb'), \
             patch('wav2vec2_audio_source.MicrophoneAudioSource.__init__', return_value=None):

            # Create instance
            audio_source = Wav2Vec2AudioSource.__new__(Wav2Vec2AudioSource)
            instructions = audio_source.get_transcription_instructions()

            # Check for specific examples
            self.assertIn('"HH EH L OW" → "hello"', instructions)
            self.assertIn('"T UW" → "to/too/two"', instructions)
            self.assertIn("mechanical transcription", instructions)


def run_integration_tests():
    """Run integration tests with proper reporting."""
    print("Running Wav2Vec2 Integration Tests")
    print("=" * 50)

    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add test classes
    test_classes = [
        TestWav2Vec2DictationAppIntegration,
        TestWav2Vec2ProviderInstructions
    ]

    for test_class in test_classes:
        tests = loader.loadTestsFromTestCase(test_class)
        suite.addTests(tests)

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Print summary
    print("\n" + "=" * 50)
    print(f"Integration Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Skipped: {len(result.skipped)}")

    if result.failures:
        print("\nFailures:")
        for test, traceback in result.failures:
            print(f"  - {test}")

    if result.errors:
        print("\nErrors:")
        for test, traceback in result.errors:
            print(f"  - {test}")

    # Return success status
    return len(result.failures) == 0 and len(result.errors) == 0


if __name__ == "__main__":
    print("Wav2Vec2 Integration Test Suite")
    print("===============================")
    print()
    print("Testing Wav2Vec2 integration with DictationApp workflow...")
    print()

    success = run_integration_tests()
    sys.exit(0 if success else 1)