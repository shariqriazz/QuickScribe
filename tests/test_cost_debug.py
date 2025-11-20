#!/usr/bin/env python3
"""Test cost output with debug enabled."""

import unittest
import sys
import io
from unittest.mock import Mock
from lib.pr_log import set_log_level, PR_DEBUG, PR_INFO, pr_debug, pr_info, get_streaming_handler


class TestCostOutput(unittest.TestCase):

    def test_log_level_setting(self):
        """Test that log level can be set to DEBUG and messages appear."""
        old_stderr = sys.stderr
        sys.stderr = io.StringIO()

        set_log_level(PR_DEBUG)
        pr_debug("Debug message test")
        pr_info("Info message test")

        output = sys.stderr.getvalue()
        sys.stderr = old_stderr

        self.assertIn("Debug message", output)
        self.assertIn("Info message", output)

    def test_cost_display_gating_disabled(self):
        """Test that _display_cache_stats returns early when debug_enabled=False."""
        from providers.base_provider import BaseProvider

        mock_config = Mock()
        mock_config.debug_enabled = False
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
        provider._display_cache_stats(mock_usage, completion_response=None)

        output = sys.stderr.getvalue()
        sys.stderr = old_stderr

        self.assertNotIn("USAGE", output)
        self.assertNotIn("COST", output)

    def test_cost_display_gating_enabled(self):
        """Test that _display_cache_stats shows output when debug_enabled=True."""
        from providers.base_provider import BaseProvider

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
        provider._display_cache_stats(mock_usage, completion_response=None)

        output = sys.stderr.getvalue()
        sys.stderr = old_stderr

        self.assertIn("USAGE", output)
        self.assertIn("Prompt tokens: 100", output)
        self.assertIn("Completion tokens: 50", output)

    def test_streaming_message_queue(self):
        """Test that debug messages are queued during streaming and flushed after."""
        old_stderr = sys.stderr
        sys.stderr = io.StringIO()

        set_log_level(PR_DEBUG)

        pr_info("Before streaming")

        with get_streaming_handler() as stream:
            pr_info("During streaming")
            pr_debug("Debug during streaming")
            stream.write("Stream content")

        pr_info("After streaming")

        output = sys.stderr.getvalue()
        sys.stderr = old_stderr

        self.assertIn("Before streaming", output)
        self.assertIn("During streaming", output)
        self.assertIn("Debug during streaming", output)
        self.assertIn("After streaming", output)


if __name__ == '__main__':
    unittest.main()
