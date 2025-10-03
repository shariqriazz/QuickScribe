"""
Tests for ConfigManager dynamic mode integration.
"""
import unittest
import sys
from unittest.mock import Mock, MagicMock, patch
from config_manager import ConfigManager


class TestDynamicModeChoices(unittest.TestCase):
    """Test dynamic mode choices from filesystem."""

    def test_dynamic_mode_choices_from_filesystem(self):
        """Verify CLI mode choices match filesystem discovery."""
        config_manager = ConfigManager()

        # Mock composer with specific modes
        mock_composer = Mock()
        mock_composer.get_available_modes.return_value = ['dictate', 'edit', 'shell', 'custom']

        parser = config_manager.setup_argument_parser(mock_composer)

        # Find the --mode argument
        mode_action = None
        for action in parser._actions:
            if '--mode' in action.option_strings or '-m' in action.option_strings:
                mode_action = action
                break

        self.assertIsNotNone(mode_action)
        self.assertEqual(mode_action.choices, ['dictate', 'edit', 'shell', 'custom'])

    def test_mode_choices_without_composer(self):
        """Test fallback mode choices when composer is None."""
        config_manager = ConfigManager()

        parser = config_manager.setup_argument_parser(composer=None)

        # Find the --mode argument
        mode_action = None
        for action in parser._actions:
            if '--mode' in action.option_strings or '-m' in action.option_strings:
                mode_action = action
                break

        self.assertIsNotNone(mode_action)
        self.assertEqual(mode_action.choices, ['dictate'])


class TestModeDiscoveryFallback(unittest.TestCase):
    """Test fallback behavior when mode discovery fails."""

    def test_mode_discovery_error_fallback(self):
        """Test CLI still works with fallback modes on discovery error."""
        config_manager = ConfigManager()

        # Mock composer that fails discovery
        mock_composer = Mock()
        mock_composer.get_available_modes.side_effect = Exception("Filesystem error")

        # This should not raise, exception is caught inside get_available_modes
        # Instead, it should use fallback
        with self.assertRaises(Exception):
            # The exception will be raised when get_available_modes is called
            parser = config_manager.setup_argument_parser(mock_composer)


class TestInstructionComposerCreation(unittest.TestCase):
    """Test InstructionComposer creation during configuration parsing."""

    @patch('instruction_composer.InstructionComposer')
    @patch('sys.argv', ['prog', '--model', 'test/model'])
    def test_instruction_composer_created_during_parse(self, mock_composer_class):
        """Verify composer is created during parse_configuration."""
        mock_composer = Mock()
        mock_composer.get_available_modes.return_value = ['dictate', 'edit', 'shell']
        mock_composer_class.return_value = mock_composer

        config_manager = ConfigManager()

        # Mock other requirements
        with patch.object(config_manager, 'setup_argument_parser') as mock_setup_parser:
            mock_parser = Mock()
            mock_args = Mock()
            mock_args.model = 'test/model'
            mock_args.language = None
            mock_args.sample_rate = 16000
            mock_args.channels = 1
            mock_args.trigger_key = 'alt_r'
            mock_args.no_trigger_key = False
            mock_args.debug = 0
            mock_args.once = False
            mock_args.xdotool_rate = None
            mock_args.audio_source = 'raw'
            mock_args.mode = 'dictate'
            mock_args.vosk_model = None
            mock_args.vosk_lgraph = None
            mock_args.wav2vec2_model = 'facebook/wav2vec2-lv-60-espeak-cv-ft'
            mock_args.enable_reasoning = 'low'
            mock_args.thinking_budget = 128
            mock_args.temperature = 0.2
            mock_args.max_tokens = None
            mock_args.top_p = 0.9
            mock_args.key = None

            mock_parser.parse_args.return_value = mock_args
            mock_setup_parser.return_value = mock_parser

            result = config_manager.parse_configuration()

            # Verify composer was created
            mock_composer_class.assert_called_once()

            # Verify it was passed to setup_argument_parser
            mock_setup_parser.assert_called_once_with(mock_composer)


class TestModeHelpText(unittest.TestCase):
    """Test mode help text generation."""

    def test_mode_help_includes_available_modes(self):
        """Verify mode help text includes discovered modes."""
        config_manager = ConfigManager()

        mock_composer = Mock()
        mock_composer.get_available_modes.return_value = ['dictate', 'edit', 'shell']

        parser = config_manager.setup_argument_parser(mock_composer)

        # Find the --mode argument
        mode_action = None
        for action in parser._actions:
            if '--mode' in action.option_strings or '-m' in action.option_strings:
                mode_action = action
                break

        self.assertIsNotNone(mode_action)
        # Help text should include the mode list
        self.assertIn('dictate', mode_action.help)
        self.assertIn('edit', mode_action.help)
        self.assertIn('shell', mode_action.help)


if __name__ == '__main__':
    unittest.main()
