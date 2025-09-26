#!/usr/bin/env python3
"""
Test incremental streaming behavior of TranscriptionService.
"""

import sys
import os
import unittest
from unittest.mock import Mock, patch

# Add parent directory to path
parent_dir = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, parent_dir)
sys.path.append(os.path.join(parent_dir, 'lib', 'xml-stream'))

from xml_stream_processor import XMLStreamProcessor
from keyboard_injector import MockKeyboardInjector
from transcription_service import TranscriptionService


class TestIncrementalStreaming(unittest.TestCase):
    """Test incremental streaming behavior after <update> tag."""
    
    def setUp(self):
        """Set up test environment."""
        self.service = TranscriptionService(use_xdotool=False)
        # Access the mock keyboard directly
        self.keyboard = self.service.keyboard
        
    def test_incremental_streaming_after_update(self):
        """Test that content streams incrementally after <update> tag."""
        # Reset processor
        self.service.processor.reset({})
        
        # Send first chunk with opening update tag and complete word
        chunk1 = '<update><10>Hello </10>'
        self.service.process_streaming_chunk(chunk1)
        
        # At this point, the complete tag should be processed
        self.assertEqual(self.keyboard.output, "Hello ")
        
        # Send next chunk with another complete word
        chunk2 = '<20>world </20>'
        self.service.process_streaming_chunk(chunk2)
        
        # Now should have both words
        self.assertEqual(self.keyboard.output, "Hello world ")
        
    def test_reset_during_streaming(self):
        """Test reset handling during incremental stream."""
        self.service.processor.reset({10: "Old ", 20: "text "})
        
        # Start streaming
        chunk1 = '<update><10>New '
        self.service.process_streaming_chunk(chunk1)
        
        # Send reset mid-stream
        chunk2 = '<reset/>'
        self.service.process_streaming_chunk(chunk2)
        
        # Continue after reset
        chunk3 = '<update><10>Fresh </10>'
        self.service.process_streaming_chunk(chunk3)
        
        # Should only have content after reset
        self.assertEqual(self.keyboard.output, "Fresh ")
        
    def test_no_processing_before_update_tag(self):
        """Test that content before <update> tag is not processed."""
        self.service.processor.reset({})
        
        # Send content without update tag
        chunk1 = '<10>Hello </10>'
        self.service.process_streaming_chunk(chunk1)
        
        # Should not process yet
        self.assertEqual(self.keyboard.output, "")
        
        # Now send update tag
        chunk2 = '<update><20>World </20>'
        self.service.process_streaming_chunk(chunk2)
        
        # Now should process content after update
        self.assertEqual(self.keyboard.output, "World ")
        
    def test_multiple_update_tags_in_stream(self):
        """Test handling of multiple <update> tags in stream."""
        self.service.processor.reset({})
        
        # First update
        chunk1 = '<update><10>First </10></update>'
        self.service.process_streaming_chunk(chunk1)
        self.assertEqual(self.keyboard.output, "First ")
        
        # Reset keyboard to test next update
        self.keyboard.reset()
        self.service.processor.reset({})
        self.service.reset_streaming_state()
        
        # Second update in same session
        chunk2 = '<update><10>Second </10>'
        self.service.process_streaming_chunk(chunk2)
        self.assertEqual(self.keyboard.output, "Second ")
        
    def test_streaming_with_existing_words(self):
        """Test streaming with existing words in processor."""
        # Start with some existing words
        initial_words = {10: "The ", 20: "quick ", 30: "brown "}
        self.service.processor.reset(initial_words)
        
        # Start streaming update with complete tag
        chunk1 = '<update><20>fast </20>'
        self.service.process_streaming_chunk(chunk1)
        
        # Should have triggered backspace and started rewriting
        operations = self.keyboard.operations
        self.assertTrue(any(op[0] == 'bksp' for op in operations))
        
        # Continue streaming with another complete tag
        chunk2 = '<30>red </30>'
        self.service.process_streaming_chunk(chunk2)
        
        # With incremental emission:
        # First chunk: word 20 changes, emits "fast " only
        # Second chunk: word 30 changes, emits "red " only (no gap-fill needed since 30 is being updated)
        # Result: "fast " + "red " = "fast red "
        self.assertEqual(self.keyboard.output, "fast red ")
        
    def test_partial_tags_across_chunks(self):
        """Test partial XML tags split across streaming chunks."""
        self.service.processor.reset({})
        
        # Start with partial update tag
        chunk1 = '<upd'
        self.service.process_streaming_chunk(chunk1)
        
        # Complete update tag and start word tag
        chunk2 = 'ate><1'
        self.service.process_streaming_chunk(chunk2)
        
        # Complete word tag
        chunk3 = '0>Test</10>'
        self.service.process_streaming_chunk(chunk3)
        
        # Should have processed the word
        self.assertEqual(self.keyboard.output, "Test")
        
    def test_state_tracking_across_chunks(self):
        """Test that state is properly tracked across streaming chunks."""
        self.service.processor.reset({})
        
        # First chunk sets up the update
        chunk1 = '<update>'
        self.service.process_streaming_chunk(chunk1)
        
        # Check state
        self.assertTrue(self.service.update_seen)
        self.assertEqual(self.service.last_update_position, 8)  # len('<update>')
        
        # Add content
        chunk2 = '<10>Word</10>'
        self.service.process_streaming_chunk(chunk2)
        
        # Check state updated
        self.assertEqual(self.service.last_update_position, len('<update><10>Word</10>'))
        self.assertEqual(self.keyboard.output, "Word")


if __name__ == '__main__':
    unittest.main()