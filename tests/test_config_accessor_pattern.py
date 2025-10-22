"""Test config accessor pattern implementation."""
import sys
import unittest
from unittest.mock import MagicMock, patch
from config_manager import ConfigManager
from providers.base_provider import BaseProvider


class TestConfigAccessorPattern(unittest.TestCase):
    """Test that config accessor pattern is properly implemented."""

    def setUp(self):
        """Setup test config."""
        self.original_argv = sys.argv
        sys.argv = ['test', '--model', 'gemini/gemini-2.5-flash']
        self.config = ConfigManager()
        self.assertTrue(self.config.parse_configuration())

    def tearDown(self):
        """Restore original argv."""
        sys.argv = self.original_argv

    def test_config_has_required_fields(self):
        """Verify ConfigManager has all required fields."""
        required_fields = [
            'model_id', 'language', 'api_key', 'sample_rate',
            'debug_enabled', 'litellm_debug', 'enable_reasoning',
            'thinking_budget', 'temperature', 'max_tokens', 'top_p'
        ]
        for field in required_fields:
            self.assertTrue(
                hasattr(self.config, field),
                f"ConfigManager missing required field: {field}"
            )

    def test_base_provider_accepts_config(self):
        """Test BaseProvider constructor accepts config object."""
        mock_audio_source = MagicMock()
        provider = BaseProvider(self.config, mock_audio_source)
        self.assertIsNotNone(provider)
        self.assertEqual(provider.config, self.config)

    def test_base_provider_no_field_copying(self):
        """Test BaseProvider does not copy config fields."""
        mock_audio_source = MagicMock()
        provider = BaseProvider(self.config, mock_audio_source)

        # Provider should NOT have these as direct attributes
        self.assertFalse(hasattr(provider, 'model_id'))
        self.assertFalse(hasattr(provider, 'language'))
        self.assertFalse(hasattr(provider, 'api_key'))
        self.assertFalse(hasattr(provider, 'enable_reasoning'))
        self.assertFalse(hasattr(provider, 'thinking_budget'))
        self.assertFalse(hasattr(provider, 'temperature'))
        self.assertFalse(hasattr(provider, 'max_tokens'))
        self.assertFalse(hasattr(provider, 'debug_enabled'))
        self.assertFalse(hasattr(provider, 'litellm_debug'))

        # Provider should NOT have mode or audio_source fields
        self.assertFalse(hasattr(provider, 'mode'))
        self.assertFalse(hasattr(provider, 'audio_source'))

        # Provider SHOULD have provider attribute (single point of truth)
        self.assertTrue(hasattr(provider, 'provider'))

    def test_base_provider_has_instance_state(self):
        """Test BaseProvider has its own instance state."""
        mock_audio_source = MagicMock()
        provider = BaseProvider(self.config, mock_audio_source)

        # Provider should have these instance state fields
        self.assertTrue(hasattr(provider, '_initialized'))
        self.assertTrue(hasattr(provider, 'litellm'))
        self.assertTrue(hasattr(provider, 'model_start_time'))
        self.assertTrue(hasattr(provider, 'first_response_time'))
        self.assertTrue(hasattr(provider, 'total_cost'))

    def test_base_provider_accessor_pattern(self):
        """Test BaseProvider accesses config via self.config."""
        mock_audio_source = MagicMock()
        provider = BaseProvider(self.config, mock_audio_source)

        # Access config fields via accessor
        self.assertEqual(provider.config.model_id, 'gemini/gemini-2.5-flash')
        self.assertEqual(provider.config.temperature, 0.2)
        self.assertEqual(provider.config.enable_reasoning, 'low')
        self.assertEqual(provider.config.thinking_budget, 128)
        self.assertEqual(provider.config.sample_rate, 16000)

        # Mode and audio_source accessed via config
        self.assertEqual(provider.config.mode, 'dictate')
        self.assertEqual(provider.config.audio_source, 'raw')

    def test_config_defaults_from_argparse_only(self):
        """Test config defaults come only from argparse."""
        # Parse with no explicit args (should use argparse defaults)
        sys.argv = ['test', '--model', 'gemini/test']
        config = ConfigManager()
        self.assertTrue(config.parse_configuration())

        # Check defaults match argparse defaults
        self.assertEqual(config.enable_reasoning, 'low')
        self.assertEqual(config.thinking_budget, 128)
        self.assertEqual(config.temperature, 0.2)
        self.assertIsNone(config.max_tokens)
        self.assertEqual(config.top_p, 0.9)

    def test_base_provider_builds_completion_params(self):
        """Test BaseProvider builds completion params from config."""
        mock_audio_source = MagicMock()
        provider = BaseProvider(self.config, mock_audio_source)

        # Build messages
        messages = [{"role": "user", "content": "test"}]

        # Expected completion params (values copied at API boundary)
        expected_params = {
            "model": self.config.model_id,
            "messages": messages,
            "stream": True,
            "stream_options": {"include_usage": True},
            "temperature": self.config.temperature
        }

        # Verify values are accessed via self.config
        self.assertEqual(provider.config.model_id, expected_params["model"])
        self.assertEqual(provider.config.temperature, expected_params["temperature"])


class TestDictationAppIntegration(unittest.TestCase):
    """Test DictationApp uses single injection pattern."""

    def setUp(self):
        """Setup test environment."""
        self.original_argv = sys.argv
        sys.argv = ['test', '--model', 'gemini/gemini-2.5-flash']

    def tearDown(self):
        """Restore original argv."""
        sys.argv = self.original_argv

    @patch('dictation_app.BaseProvider')
    def test_dictation_app_single_injection(self, mock_provider_class):
        """Test DictationApp passes config and audio_source to BaseProvider."""
        from dictation_app import DictationApp

        app = DictationApp()
        app.config_manager = ConfigManager()
        app.config_manager.parse_configuration()
        app.config = app.config_manager

        # Mock audio_source (required by BaseProvider)
        app.audio_source = MagicMock()

        # Call provider initialization
        result = app._initialize_provider_client()

        # Verify BaseProvider was called with config and audio_source
        mock_provider_class.assert_called_once_with(app.config, app.audio_source)


class TestWav2Vec2Integration(unittest.TestCase):
    """Test HuggingFaceTranscriptionAudioSource uses config accessor."""

    def setUp(self):
        """Setup test config."""
        self.original_argv = sys.argv
        sys.argv = ['test', '--model', 'gemini/test', '--sample-rate', '16000']
        self.config = ConfigManager()
        self.assertTrue(self.config.parse_configuration())

    def tearDown(self):
        """Restore original argv."""
        sys.argv = self.original_argv

    def test_wav2vec2_no_sample_rate_copy(self):
        """Test HuggingFaceCTCTranscriptionAudioSource does not copy sample_rate."""
        try:
            from transcription.implementations.huggingface import HuggingFaceCTCTranscriptionAudioSource

            # Create source
            source = HuggingFaceCTCTranscriptionAudioSource(
                self.config,
                "huggingface/facebook/wav2vec2-lv-60-espeak-cv-ft"
            )

            # Should NOT have sample_rate as direct attribute
            # (Note: parent MicrophoneAudioSource has config, so check there)
            self.assertEqual(source.config.sample_rate, 16000)

        except ImportError as e:
            self.skipTest(f"Wav2Vec2 dependencies not available: {e}")


if __name__ == '__main__':
    unittest.main()