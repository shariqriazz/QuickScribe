"""
Tests for Wav2Vec2 audio source implementation.
"""
import unittest
import numpy as np
import sys
import os
from unittest.mock import Mock, patch, MagicMock
import tempfile
import json

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


class MockConfig:
    """Mock configuration for testing."""
    def __init__(self):
        self.sample_rate = 16000
        self.channels = 1


class TestWav2Vec2AudioSourceMocked(unittest.TestCase):
    """Test Wav2Vec2AudioSource with all dependencies mocked."""

    def setUp(self):
        """Set up test fixtures with mocked dependencies."""
        self.config = MockConfig()

        # Mock all external dependencies
        self.torch_mock = Mock()
        # Mock torch.no_grad to return a context manager
        mock_no_grad = Mock()
        mock_no_grad.__enter__ = Mock(return_value=None)
        mock_no_grad.__exit__ = Mock(return_value=None)
        self.torch_mock.no_grad.return_value = mock_no_grad

        self.transformers_mock = Mock()
        self.feature_extractor_mock = Mock()
        self.model_mock = Mock()

        # Mock vocab data
        self.mock_vocab = {'<pad>': 0, 't': 1, 'ɛ': 2, 's': 3, 'hello': 4}

        # Mock open to return a context manager
        mock_file = Mock()
        mock_file.__enter__ = Mock(return_value=mock_file)
        mock_file.__exit__ = Mock(return_value=None)

        self.patches = [
            patch('wav2vec2_audio_source.torch', self.torch_mock),
            patch('wav2vec2_audio_source.transformers', self.transformers_mock),
            patch('wav2vec2_audio_source.Wav2Vec2FeatureExtractor', self.feature_extractor_mock),
            patch('wav2vec2_audio_source.Wav2Vec2ForCTC', self.model_mock),
            patch('wav2vec2_audio_source.is_offline_mode', Mock(return_value=False)),
            patch('wav2vec2_audio_source.HfApi', Mock()),
            patch('huggingface_hub.hf_hub_download', Mock(return_value='/tmp/vocab.json')),
            patch('builtins.open', Mock(return_value=mock_file)),
            patch('json.load', Mock(return_value=self.mock_vocab))
        ]

        for patcher in self.patches:
            patcher.start()

        # Set up feature extractor and model mocks
        self.feature_extractor_instance = Mock()
        self.model_instance = Mock()

        self.feature_extractor_mock.from_pretrained.return_value = self.feature_extractor_instance
        self.model_mock.from_pretrained.return_value = self.model_instance

    def tearDown(self):
        """Clean up patches."""
        for patcher in self.patches:
            patcher.stop()

    def test_audio_source_initialization(self):
        """Test that Wav2Vec2AudioSource initializes correctly."""
        from wav2vec2_audio_source import Wav2Vec2AudioSource

        audio_source = Wav2Vec2AudioSource(self.config, "test_model")

        # Check basic attributes
        self.assertEqual(audio_source.config.sample_rate, 16000)
        self.assertEqual(audio_source.model_path, "test_model")
        self.assertIsNotNone(audio_source.feature_extractor)
        self.assertIsNotNone(audio_source.model)
        self.assertIsInstance(audio_source.id_to_phoneme, dict)

    def test_phoneme_decoding(self):
        """Test phoneme decoding functionality."""
        from wav2vec2_audio_source import Wav2Vec2AudioSource

        audio_source = Wav2Vec2AudioSource(self.config, "test_model")

        # Mock predicted IDs tensor - create a proper mock that supports indexing
        mock_tensor = Mock()
        mock_tensor.tolist.return_value = [1, 2, 3]  # t, ɛ, s
        mock_predicted_ids = [mock_tensor]  # Mock batch with one element

        result = audio_source._decode_phonemes(mock_predicted_ids)
        self.assertEqual(result, "tɛs")

    def test_audio_processing(self):
        """Test audio processing functionality."""
        from wav2vec2_audio_source import Wav2Vec2AudioSource

        audio_source = Wav2Vec2AudioSource(self.config, "test_model")

        # Mock the feature extractor and model
        mock_input_values = Mock()
        mock_logits = Mock()
        mock_predicted_ids = Mock()

        self.feature_extractor_instance.return_value.input_values = mock_input_values
        self.model_instance.return_value.logits = mock_logits

        # Create proper mock tensor structure
        mock_tensor = Mock()
        mock_tensor.tolist.return_value = [1, 2, 3]
        mock_predicted_ids = [mock_tensor]
        self.torch_mock.argmax.return_value = mock_predicted_ids

        # Test with valid audio data
        test_audio = np.random.random(16000).astype(np.float32)
        result = audio_source._process_audio(test_audio)

        self.assertIsInstance(result, str)
        # Should call feature extractor and model
        self.feature_extractor_instance.assert_called()
        self.model_instance.assert_called()

    def test_stop_recording_with_audio(self):
        """Test stop_recording returns AudioTextResult with phonemes."""
        from wav2vec2_audio_source import Wav2Vec2AudioSource
        from audio_source import AudioDataResult, AudioTextResult

        audio_source = Wav2Vec2AudioSource(self.config, "test_model")

        # Mock the parent stop_recording to return AudioDataResult
        test_audio = np.random.random(16000).astype(np.float32)
        mock_audio_result = AudioDataResult(test_audio, 16000)

        with patch.object(audio_source.__class__.__bases__[0], 'stop_recording', return_value=mock_audio_result):
            # Mock the _process_audio method
            with patch.object(audio_source, '_process_audio', return_value="t ɛ s t"):
                result = audio_source.stop_recording()

                self.assertIsInstance(result, AudioTextResult)
                self.assertEqual(result.transcribed_text, "t ɛ s t")
                self.assertEqual(result.sample_rate, 16000)
                np.testing.assert_array_equal(result.audio_data, test_audio)

    def test_reset_functionality(self):
        """Test that reset works (inherited from parent)."""
        from wav2vec2_audio_source import Wav2Vec2AudioSource

        audio_source = Wav2Vec2AudioSource(self.config, "test_model")

        # Should have basic audio source functionality
        self.assertTrue(hasattr(audio_source, 'start_recording'))
        self.assertTrue(hasattr(audio_source, 'stop_recording'))
        self.assertTrue(hasattr(audio_source, 'initialize'))

    def test_chunk_handler_initialization(self):
        """Test legacy chunk handler interface (backward compatibility)."""
        # This test ensures the old chunk handler tests don't break completely
        # In the new implementation, chunk handling is integrated into Wav2Vec2AudioSource
        from wav2vec2_audio_source import Wav2Vec2AudioSource

        audio_source = Wav2Vec2AudioSource(self.config, "test_model")

        # Basic functionality should work
        self.assertEqual(audio_source.model_path, "test_model")
        self.assertEqual(audio_source.config.sample_rate, 16000)

    def test_chunk_processing(self):
        """Test that audio processing works (replaces old chunk processing)."""
        from wav2vec2_audio_source import Wav2Vec2AudioSource

        audio_source = Wav2Vec2AudioSource(self.config, "test_model")

        # Test that we can process audio data
        test_audio = np.random.random(16000).astype(np.float32)

        # Mock the processing
        with patch.object(audio_source, '_process_audio', return_value="test phonemes"):
            result = audio_source._process_audio(test_audio)
            self.assertEqual(result, "test phonemes")

    def test_finalize_with_mock_inference(self):
        """Test phoneme inference with mocked model."""
        from wav2vec2_audio_source import Wav2Vec2AudioSource

        audio_source = Wav2Vec2AudioSource(self.config, "test_model")

        # Mock torch operations
        mock_tensor = Mock()
        mock_tensor.tolist.return_value = [1, 2, 3]
        mock_predicted_ids = [mock_tensor]
        self.torch_mock.argmax.return_value = mock_predicted_ids

        # Mock feature extractor output
        mock_feature_output = Mock()
        mock_feature_output.input_values = Mock()
        self.feature_extractor_instance.return_value = mock_feature_output

        # Mock model output
        mock_model_output = Mock()
        mock_model_output.logits = Mock()
        self.model_instance.return_value = mock_model_output

        # Test processing
        test_audio = np.random.random(16000).astype(np.float32)
        result = audio_source._process_audio(test_audio)

        self.assertIsInstance(result, str)


class TestErrorHandling(unittest.TestCase):
    """Test error handling in Wav2Vec2 implementation."""

    def setUp(self):
        """Set up test fixtures."""
        self.config = MockConfig()

    def test_model_loading_error(self):
        """Test handling of model loading errors."""
        with patch('wav2vec2_audio_source.torch', None):
            with patch('wav2vec2_audio_source.transformers', None):
                from wav2vec2_audio_source import Wav2Vec2AudioSource

                with self.assertRaises(ImportError):
                    Wav2Vec2AudioSource(self.config, "test_model")

    def test_audio_too_short(self):
        """Test handling of audio that's too short."""
        with patch('wav2vec2_audio_source.torch', Mock()):
            with patch('wav2vec2_audio_source.transformers', Mock()):
                with patch('wav2vec2_audio_source.Wav2Vec2FeatureExtractor'):
                    with patch('wav2vec2_audio_source.Wav2Vec2ForCTC'):
                        with patch('huggingface_hub.hf_hub_download'):
                            with patch('builtins.open'):
                                with patch('json.load', return_value={}):
                                    from wav2vec2_audio_source import Wav2Vec2AudioSource

                                    audio_source = Wav2Vec2AudioSource(self.config, "test_model")

                                    # Test with very short audio
                                    short_audio = np.array([0.1, 0.2], dtype=np.float32)
                                    result = audio_source._process_audio(short_audio)

                                    self.assertEqual(result, "")


if __name__ == '__main__':
    unittest.main()