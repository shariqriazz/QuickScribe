#!/usr/bin/env python3
"""
Test case that reproduces the exact condition where complete_stream fails to call end_stream.
"""

import sys
import os
import unittest
from unittest.mock import Mock

# Add parent directory to path
parent_dir = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, parent_dir)
sys.path.append(os.path.join(parent_dir, 'lib', 'xml-stream'))

from xml_stream_processor import XMLStreamProcessor
from keyboard_injector import MockKeyboardInjector
from transcription_service import TranscriptionService


class TestStreamCompletionFix(unittest.TestCase):
    """Test the exact condition that causes complete_stream to fail."""

    def setUp(self):
        """Set up test environment."""
        class MockConfig:
            debug_enabled = True
            xml_stream_debug = False

        self.config = MockConfig()
        self.service = TranscriptionService(self.config)
        # Replace with MockKeyboardInjector for testing
        from keyboard_injector import MockKeyboardInjector
        self.keyboard = MockKeyboardInjector()
        self.service.keyboard = self.keyboard
        self.service.processor.keyboard = self.keyboard

    def test_complete_stream_when_streaming_inactive_but_words_pending(self):
        """
        Test the specific case where streaming_active is False but there are still words to emit.
        This reproduces the user's exact issue.
        """
        # Reset processor with initial words
        self.service.processor.reset({10: "Hello ", 20: "world ", 30: "from ", 40: "Python!"})

        # Simulate a streaming session that processes some words but not all
        self.service.processor.start_stream()

        # Process only the first two words, leaving 30 and 40 unprocessed
        self.service.processor.process_chunk('<10>Hi </10>')

        # At this point we should have: "Hi " emitted, but words 20, 30, 40 are pending
        self.assertEqual(self.keyboard.output, "Hi ")

        # Now manually end the stream (simulating model completion)
        self.service.processor.end_stream()

        # After end_stream, streaming_active should be False
        self.assertFalse(self.service.processor.streaming_active)

        # But we should have all remaining words emitted
        self.assertEqual(self.keyboard.output, "Hi world from Python!")

        # Reset keyboard to test complete_stream behavior
        self.keyboard.reset()

        # Set up the scenario again, but this time test complete_stream
        self.service.processor.reset({})  # Start fresh
        self.service.reset_streaming_state()

        # Simulate streaming that processes some words
        self.service.process_streaming_chunk('<update><10>Hi </10>')
        self.assertEqual(self.keyboard.output, "Hi ")

        # Manually set streaming_active to False (simulating what happens when model exits)
        self.service.processor.streaming_active = False

        # Add remaining content to streaming buffer (like content that arrived after model stopped)
        self.service.streaming_buffer += '<20>there </20><30>friend</30></update>'

        # Now call complete_stream - this should process the remaining content and emit it
        self.service.complete_stream()

        # Should have emitted all words
        expected = "Hi there friend"
        self.assertEqual(self.keyboard.output, expected)

    def test_complete_stream_should_check_pending_words_not_streaming_active(self):
        """
        Test that complete_stream should check for pending words, not just streaming_active.
        """
        # Set up processor with words where some haven't been emitted
        self.service.processor.reset({10: "The ", 20: "quick ", 30: "brown ", 40: "fox"})

        # Simulate processing that only emits some words
        self.service.processor.start_stream()
        self.service.processor.process_chunk('<10>A </10><20>fast </20>')

        # Should have: "A fast " emitted, "brown fox" pending (last_emitted_seq = 20, max_seq = 40)
        self.assertEqual(self.keyboard.output, "A fast ")
        self.assertEqual(self.service.processor.last_emitted_seq, 20)

        # Manually set streaming_active to False
        self.service.processor.streaming_active = False

        # complete_stream should still call end_stream because there are pending words
        self.service.complete_stream()

        # Should have all words emitted
        self.assertEqual(self.keyboard.output, "A fast brown fox")


if __name__ == '__main__':
    unittest.main(verbosity=2)