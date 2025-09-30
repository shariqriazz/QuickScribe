#!/usr/bin/env python3
"""
Test case that reproduces the stream completion bug where final chunks aren't emitted.
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


class TestStreamCompletionBug(unittest.TestCase):
    """Test the exact stream completion issue where final chunks aren't emitted."""

    def setUp(self):
        """Set up test environment."""
        class MockConfig:
            debug_enabled = True

        self.config = MockConfig()
        self.service = TranscriptionService(self.config)
        # Replace with MockKeyboardInjector for testing
        from keyboard_injector import MockKeyboardInjector
        self.keyboard = MockKeyboardInjector()
        self.service.keyboard = self.keyboard
        self.service.processor.keyboard = self.keyboard

    def test_stream_completion_with_partial_chunks(self):
        """Test that complete_stream() properly emits final chunks even when model exits early."""
        # Reset processor
        self.service.processor.reset({})

        # Simulate streaming chunks like the user's example
        chunks = [
            '<update><10>I </10>',
            '<20>think </20>',
            '<30>the </30>',
            '<40>dependency </40>',
            '<50>tree </50>',
            '<60>is </60>',
            '<70>backwards </70>',
            '<80>compared </80>',
            '<90>to </90>',
            # Model exits here before sending final chunks, but XML contains them
            '<100>the </100><110>original </110><120>script.</120></update>'
        ]

        # Process all chunks except the last one (simulating model early exit)
        for chunk in chunks[:-1]:
            self.service.process_streaming_chunk(chunk)

        # At this point we should have: "I think the dependency tree is backwards compared to "
        # But we're missing "the original script."
        current_output = self.keyboard.output
        print(f"\nAfter processing chunks (before complete_stream): '{current_output}'")

        # Now add the final chunk to the buffer (as if it arrived after model stopped)
        self.service.streaming_buffer += chunks[-1]

        # Call complete_stream - this should emit the remaining words
        self.service.complete_stream()

        final_output = self.keyboard.output
        print(f"After complete_stream: '{final_output}'")

        # Should have the complete sentence
        expected = "I think the dependency tree is backwards compared to the original script."
        self.assertEqual(final_output, expected)

    def test_stream_completion_with_malformed_tags(self):
        """Test stream completion with malformed XML tags like in user's example."""
        # Reset processor
        self.service.processor.reset({})

        # Simulate the exact malformed XML from user's report
        malformed_xml = '<update><10>I </10><20>think </20><30>the </30><40>dependency </40><50>tree </50><60>is </60><70>backwards </70><80>compared </80><90>to </90><100>the </110>original </120>script.</120></update>'

        # Process chunks incrementally
        chunks = [
            '<update><10>I </10>',
            '<20>think </20>',
            '<30>the </30>',
            '<40>dependency </40>',
            '<50>tree </50>',
            '<60>is </60>',
            '<70>backwards </70>',
            '<80>compared </80>',
            '<90>to </90>',
            # This part is malformed: <100>the </110>original </120>script.</120>
            '<100>the </110>original </120>script.</120></update>'
        ]

        # Process all but last chunk
        for chunk in chunks[:-1]:
            self.service.process_streaming_chunk(chunk)

        current_output = self.keyboard.output
        print(f"\nBefore malformed chunk: '{current_output}'")

        # Add malformed chunk to buffer
        self.service.streaming_buffer += chunks[-1]

        # Call complete_stream
        self.service.complete_stream()

        final_output = self.keyboard.output
        print(f"After complete_stream with malformed tags: '{final_output}'")

        # Should handle malformed tags gracefully and emit what it can parse
        # The regex r'<(\d+)>(.*?)</\1>' should only match properly formed tags
        self.assertIn("I think the dependency tree is backwards compared to", final_output)

    def test_complete_stream_calls_end_stream_when_needed(self):
        """Test that complete_stream calls end_stream when there are unprocessed words."""
        # Reset processor with some initial state
        self.service.processor.reset({10: "Hello ", 20: "world "})

        # Simulate streaming that changes only first word
        self.service.process_streaming_chunk('<update><10>Hi </10>')

        # At this point, only "Hi " should be emitted, "world " is pending
        self.assertEqual(self.keyboard.output, "Hi ")

        # complete_stream should call end_stream to flush remaining words
        self.service.complete_stream()

        # Should now have both words
        self.assertEqual(self.keyboard.output, "Hi world ")

    def test_complete_stream_respects_backspace_state(self):
        """Test that complete_stream only calls end_stream when backspace was performed."""
        # Reset processor
        self.service.processor.reset({})

        # Add content without triggering backspace (no changes to existing words)
        self.service.process_streaming_chunk('<update><10>New </10>')

        # This should emit immediately since no backspace needed
        self.assertEqual(self.keyboard.output, "New ")

        # complete_stream should not do anything extra since no backspace was performed
        self.service.complete_stream()

        # Output should remain the same
        self.assertEqual(self.keyboard.output, "New ")


if __name__ == '__main__':
    unittest.main(verbosity=2)