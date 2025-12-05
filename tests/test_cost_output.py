#!/usr/bin/env python3
"""Test cost output with debug enabled."""

import sys
import io
from unittest.mock import Mock, MagicMock
from lib.pr_log import set_log_level, PR_DEBUG, PR_INFO, pr_debug, pr_info


def test_log_level_setting():
    """Test that log level can be set to DEBUG."""
    print("Test 1: Log level setting")
    print(f"  PR_DEBUG={PR_DEBUG}, PR_INFO={PR_INFO}")

    # Capture stderr
    old_stderr = sys.stderr
    sys.stderr = io.StringIO()

    # Test with DEBUG level
    set_log_level(PR_DEBUG)
    pr_debug("Debug message test")
    pr_info("Info message test")

    output = sys.stderr.getvalue()
    sys.stderr = old_stderr

    print(f"  Output with PR_DEBUG level:")
    print(f"    {repr(output)}")
    print(f"    Contains 'Debug message': {'Debug message' in output}")
    print(f"    Contains 'Info message': {'Info message' in output}")
    print()


def test_cost_display_gating():
    """Test that _display_cache_stats respects debug_enabled flag."""
    print("Test 2: Cost display gating")

    # Mock config
    mock_config = Mock()
    mock_audio_processor = Mock()

    # Import after mocking to avoid initialization issues
    from providers.base_provider import BaseProvider

    # Test with debug_enabled=False
    mock_config.debug_enabled = False
    mock_config.model_id = "anthropic/test-model"
    mock_config.api_key = None
    mock_config.litellm_debug = False
    mock_config.sample_rate = 16000

    provider = BaseProvider(mock_config, mock_audio_processor)

    # Mock usage data
    mock_usage = Mock()
    mock_usage.prompt_tokens = 100
    mock_usage.completion_tokens = 50
    mock_usage.total_tokens = 150

    # Capture stderr
    old_stderr = sys.stderr
    sys.stderr = io.StringIO()

    set_log_level(PR_DEBUG)
    provider._display_cache_stats(mock_usage, completion_response=None)

    output_disabled = sys.stderr.getvalue()
    sys.stderr = old_stderr

    print(f"  With debug_enabled=False:")
    print(f"    Output: {repr(output_disabled)}")
    print(f"    Contains 'USAGE': {'USAGE' in output_disabled}")
    print(f"    Contains 'COST': {'COST' in output_disabled}")
    print()

    # Test with debug_enabled=True
    mock_config.debug_enabled = True
    provider2 = BaseProvider(mock_config, mock_audio_processor)

    old_stderr = sys.stderr
    sys.stderr = io.StringIO()

    set_log_level(PR_DEBUG)
    provider2._display_cache_stats(mock_usage, completion_response=None)

    output_enabled = sys.stderr.getvalue()
    sys.stderr = old_stderr

    print(f"  With debug_enabled=True:")
    print(f"    Output: {repr(output_enabled)}")
    print(f"    Contains 'USAGE': {'USAGE' in output_enabled}")
    print(f"    Contains 'COST': {'COST' in output_enabled}")
    print()


def test_streaming_message_queue():
    """Test that debug messages are queued during streaming and flushed after."""
    print("Test 3: Streaming message queue")

    from lib.pr_log import get_streaming_handler

    old_stderr = sys.stderr
    sys.stderr = io.StringIO()

    set_log_level(PR_DEBUG)

    # Messages before streaming
    pr_info("Before streaming")

    # Messages during streaming
    with get_streaming_handler() as stream:
        pr_info("During streaming - should queue")
        pr_debug("Debug during streaming - should queue")
        stream.write("Stream content")

    # Messages after streaming
    pr_info("After streaming")

    output = sys.stderr.getvalue()
    sys.stderr = old_stderr

    print(f"  Output order:")
    lines = output.split('\n')
    for i, line in enumerate(lines):
        if line.strip():
            print(f"    {i}: {repr(line)}")

    print(f"\n  Analysis:")
    print(f"    'Before streaming' appears: {'Before streaming' in output}")
    print(f"    'During streaming' appears: {'During streaming' in output}")
    print(f"    'Debug during streaming' appears: {'Debug during streaming' in output}")
    print(f"    'After streaming' appears: {'After streaming' in output}")
    print()


if __name__ == '__main__':
    print("=" * 60)
    print("Cost Output Debug Tests")
    print("=" * 60)
    print()

    test_log_level_setting()
    test_cost_display_gating()
    test_streaming_message_queue()

    print("=" * 60)
    print("Tests complete")
    print("=" * 60)
