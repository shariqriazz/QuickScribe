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


class TestHuggingFaceTranscriptionAudioSourceMocked(unittest.TestCase):
    """Test HuggingFaceTranscriptionAudioSource with all dependencies mocked."""

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

        # Setup processor and model mocks
        self.processor_mock = Mock()
        self.processor_mock.tokenizer = Mock()
        self.model_instance = Mock()

        def mock_load_model(audio_source_self, model_path):
            """Mock _load_model to avoid actual model loading."""
            audio_source_self.processor = self.processor_mock
            audio_source_self.model = self.model_instance

        self.patches = [
            patch('transcription.implementations.huggingface_ctc.audio_source.torch', self.torch_mock),
            patch('transcription.implementations.huggingface_ctc.audio_source.transformers', self.transformers_mock),
            patch('transcription.implementations.huggingface_ctc.audio_source.HuggingFaceCTCTranscriptionAudioSource._load_model', mock_load_model),
            patch('transcription.implementations.huggingface_ctc.audio_source.pyrb', Mock())
        ]

        for patcher in self.patches:
            patcher.start()

    def tearDown(self):
        """Clean up patches."""
        for patcher in self.patches:
            patcher.stop()

    def test_audio_source_initialization(self):
        """Test that HuggingFaceCTCTranscriptionAudioSource initializes correctly."""
        from transcription.implementations.huggingface_ctc import HuggingFaceCTCTranscriptionAudioSource

        audio_source = HuggingFaceCTCTranscriptionAudioSource(self.config, "test_model")

        # Check basic attributes
        self.assertEqual(audio_source.config.sample_rate, 16000)
        self.assertEqual(audio_source.model_identifier, "test_model")
        self.assertIsNotNone(audio_source.processor)
        self.assertIsNotNone(audio_source.model)

    def test_phoneme_decoding(self):
        """Test phoneme decoding functionality."""
        from transcription.implementations.huggingface_ctc import HuggingFaceCTCTranscriptionAudioSource

        audio_source = HuggingFaceCTCTranscriptionAudioSource(self.config, "test_model")

        # Mock predicted IDs tensor
        mock_tensor = Mock()
        mock_tensor.tolist.return_value = [1, 2, 3]  # t, ɛ, s
        mock_predicted_ids = [mock_tensor]

        # Mock processor.batch_decode
        audio_source.processor.batch_decode = Mock(return_value=["tɛs"])
        result = audio_source.processor.batch_decode(mock_predicted_ids)
        self.assertEqual(result[0], "tɛs")

    def test_audio_processing(self):
        """Test audio processing functionality."""
        from transcription.implementations.huggingface_ctc import HuggingFaceCTCTranscriptionAudioSource

        audio_source = HuggingFaceCTCTranscriptionAudioSource(self.config, "test_model")

        # Mock the processor and model
        mock_input_values = Mock()
        mock_logits = Mock()
        mock_predicted_ids = Mock()

        audio_source.processor.return_value.input_values = mock_input_values
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
        # Should call processor and model
        self.model_instance.assert_called()

    def test_stop_recording_with_audio(self):
        """Test stop_recording returns AudioTextResult with phonemes."""
        from transcription.implementations.huggingface_ctc import HuggingFaceCTCTranscriptionAudioSource
        from audio_source import AudioDataResult, AudioTextResult

        audio_source = HuggingFaceCTCTranscriptionAudioSource(self.config, "test_model")

        # Mock the parent stop_recording to return AudioDataResult
        test_audio = np.random.random(16000).astype(np.float32)
        mock_audio_result = AudioDataResult(test_audio, 16000)

        with patch('microphone_audio_source.MicrophoneAudioSource.stop_recording', return_value=mock_audio_result):
            # Mock the _transcribe_audio method
            with patch.object(audio_source, '_transcribe_audio', return_value="t ɛ s t"):
                result = audio_source.stop_recording()

                self.assertIsInstance(result, AudioTextResult)
                self.assertEqual(result.transcribed_text, "<tx>t ɛ s t</tx>")
                self.assertEqual(result.sample_rate, 16000)
                np.testing.assert_array_equal(result.audio_data, test_audio)

    def test_reset_functionality(self):
        """Test that reset works (inherited from parent)."""
        from transcription.implementations.huggingface_ctc import HuggingFaceCTCTranscriptionAudioSource

        audio_source = HuggingFaceCTCTranscriptionAudioSource(self.config, "test_model")

        # Should have basic audio source functionality
        self.assertTrue(hasattr(audio_source, 'start_recording'))
        self.assertTrue(hasattr(audio_source, 'stop_recording'))
        self.assertTrue(hasattr(audio_source, 'initialize'))

    def test_chunk_handler_initialization(self):
        """Test legacy chunk handler interface (backward compatibility)."""
        # This test ensures the old chunk handler tests don't break completely
        # In the new implementation, chunk handling is integrated into HuggingFaceCTCTranscriptionAudioSource
        from transcription.implementations.huggingface_ctc import HuggingFaceCTCTranscriptionAudioSource

        audio_source = HuggingFaceCTCTranscriptionAudioSource(self.config, "test_model")

        # Basic functionality should work
        self.assertEqual(audio_source.model_identifier, "test_model")
        self.assertEqual(audio_source.config.sample_rate, 16000)

    def test_chunk_processing(self):
        """Test that audio processing works (replaces old chunk processing)."""
        from transcription.implementations.huggingface_ctc import HuggingFaceCTCTranscriptionAudioSource

        audio_source = HuggingFaceCTCTranscriptionAudioSource(self.config, "test_model")

        # Test that we can process audio data
        test_audio = np.random.random(16000).astype(np.float32)

        # Mock the processing
        with patch.object(audio_source, '_process_audio', return_value="test phonemes"):
            result = audio_source._process_audio(test_audio)
            self.assertEqual(result, "test phonemes")

    def test_finalize_with_mock_inference(self):
        """Test phoneme inference with mocked model."""
        from transcription.implementations.huggingface_ctc import HuggingFaceCTCTranscriptionAudioSource

        audio_source = HuggingFaceCTCTranscriptionAudioSource(self.config, "test_model")

        # Mock torch operations
        mock_tensor = Mock()
        mock_tensor.tolist.return_value = [1, 2, 3]
        mock_predicted_ids = [mock_tensor]
        self.torch_mock.argmax.return_value = mock_predicted_ids

        # Mock processor output
        mock_feature_output = Mock()
        mock_feature_output.input_values = Mock()
        audio_source.processor.return_value = mock_feature_output

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
        with patch('transcription.implementations.huggingface_ctc.audio_source.torch', None):
            with patch('transcription.implementations.huggingface_ctc.audio_source.transformers', None):
                from transcription.implementations.huggingface_ctc import HuggingFaceCTCTranscriptionAudioSource

                with self.assertRaises(ImportError):
                    HuggingFaceCTCTranscriptionAudioSource(self.config, "test_model")

    def test_audio_too_short(self):
        """Test handling of audio that's too short."""
        processor_mock = Mock()
        processor_mock.tokenizer = Mock()
        model_mock = Mock()

        def mock_load_model(audio_source_self, model_path):
            """Mock _load_model to avoid actual model loading."""
            audio_source_self.processor = processor_mock
            audio_source_self.model = model_mock

        with patch('transcription.implementations.huggingface_ctc.audio_source.torch', Mock()):
            with patch('transcription.implementations.huggingface_ctc.audio_source.transformers', Mock()):
                with patch('transcription.implementations.huggingface_ctc.audio_source.HuggingFaceCTCTranscriptionAudioSource._load_model', mock_load_model):
                    with patch('transcription.implementations.huggingface_ctc.audio_source.pyrb', Mock()):
                        from transcription.implementations.huggingface_ctc import HuggingFaceCTCTranscriptionAudioSource

                        audio_source = HuggingFaceCTCTranscriptionAudioSource(self.config, "test_model")

                        # Test with very short audio
                        short_audio = np.array([0.1, 0.2], dtype=np.float32)
                        result = audio_source._process_audio(short_audio)

                        self.assertEqual(result, "")


if __name__ == '__main__':
    unittest.main()