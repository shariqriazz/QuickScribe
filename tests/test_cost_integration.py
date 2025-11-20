#!/usr/bin/env python3
"""Integration test for cost output in actual usage scenario."""

import unittest
import sys
import io
from unittest.mock import Mock, patch
from lib.pr_log import set_log_level, PR_DEBUG


class TestCostIntegration(unittest.TestCase):

    def test_cost_output_with_streaming_context(self):
        """Test cost output after streaming context exits."""
        from providers.base_provider import BaseProvider
        from lib.pr_log import get_streaming_handler

        mock_config = Mock()
        mock_config.debug_enabled = True
        mock_config.model_id = "anthropic/claude-3-5-sonnet-20241022"
        mock_config.api_key = None
        mock_config.litellm_debug = False
        mock_config.sample_rate = 16000

        mock_audio_processor = Mock()
        provider = BaseProvider(mock_config, mock_audio_processor)

        mock_usage = Mock()
        mock_usage.prompt_tokens = 100
        mock_usage.completion_tokens = 50
        mock_usage.total_tokens = 150

        old_stderr = sys.stderr
        sys.stderr = io.StringIO()

        set_log_level(PR_DEBUG)

        # Simulate the actual flow from _process_streaming_response
        try:
            with get_streaming_handler() as stream:
                # Simulate streaming output
                stream.write("Model output here")
                # usage_data would be captured during streaming
        except:
            pass

        # Now outside the streaming context, call _display_cache_stats
        # This is what happens at line 439 in base_provider.py
        provider._display_cache_stats(mock_usage, completion_response=None)

        output = sys.stderr.getvalue()
        sys.stderr = old_stderr

        # Debug output
        print("\n=== CAPTURED OUTPUT ===")
        print(output)
        print("=== END OUTPUT ===\n")

        # Verify cost stats appear
        self.assertIn("USAGE STATISTICS", output)
        self.assertIn("Prompt tokens: 100", output)
        self.assertIn("Completion tokens: 50", output)
        self.assertIn("Total tokens: 150", output)

    def test_debug_flag_sets_log_level(self):
        """Test that -D flag properly enables debug output."""
        from dictation_app import DictationApp
        from lib.pr_log import _current_log_level, PR_DEBUG
        import argparse

        # Mock sys.argv
        with patch('sys.argv', ['dictation_app.py', '-D', '--model', 'anthropic/test']):
            app = DictationApp()

            # Parse configuration to set debug_enabled
            app.config_manager.parse_configuration()
            app.config = app.config_manager

            # Check if debug_enabled was set
            self.assertTrue(app.config.debug_enabled)


if __name__ == '__main__':
    unittest.main(verbosity=2)
