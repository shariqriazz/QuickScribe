#!/usr/bin/env python3
"""
Test XML stream processor integration with conversation and streaming processing.
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


class TestXMLStreamConversationIntegration(unittest.TestCase):
    """Test XMLStreamProcessor integration with conversation processing."""
    
    def setUp(self):
        """Set up test environment."""
        class MockConfig:
            use_xdotool = False
            debug_enabled = False
        self.service = TranscriptionService(MockConfig())
        self.keyboard = self.service.keyboard  # Use the keyboard from the service
        
    def test_conversation_processing(self):
        """Test that conversation tags are properly detected and processed."""
        self.service.processor.reset({})
        
        # Test text with both conversation and word tags
        test_xml = '<conversation>Let me help you with that.</conversation><10>hello </10><20>world </20>'
        
        # Process the XML
        with patch('builtins.print') as mock_print:
            self.service.process_xml_transcription(test_xml)
            
            # Verify conversation was processed (printed)
            mock_print.assert_called()
            
        # Verify word processing worked
        self.assertEqual(self.keyboard.output, "hello world ")

    def test_word_only_processing(self):
        """Test processing XML with only word tags."""
        self.service.processor.reset({})
        
        # Test text with only word tags
        test_xml = '<10>hello </10><20>beautiful </20><30>world </30>'
        
        # Process the XML
        self.service.process_xml_transcription(test_xml)
        
        # Verify results
        self.assertEqual(self.keyboard.output, "hello beautiful world ")

    def test_conversation_only_processing(self):
        """Test processing XML with only conversation tags."""
        self.service.processor.reset({})
        
        # Test text with only conversation tags
        test_xml = '<conversation>This is a response from the AI assistant.</conversation>'
        
        # Process the XML
        with patch('builtins.print') as mock_print:
            self.service.process_xml_transcription(test_xml)
            
            # Verify conversation was printed
            mock_print.assert_called()
            call_args = str(mock_print.call_args_list)
            self.assertIn("AI assistant", call_args)
        
        # No word processing should occur
        self.assertEqual(self.keyboard.output, "")

    def test_streaming_chunk_processing(self):
        """Test streaming chunk processing with update tags."""
        self.service.processor.reset({})

        # Simulate streaming chunks
        chunk1 = '<update><10>Hello </10></update>'
        chunk2 = '<update><10>Hello </10><20>world </20></update>'

        # Process first chunk
        self.service.process_streaming_chunk(chunk1)
        # Verify intermediate state
        self.assertEqual(self.keyboard.output, "Hello ")

        # Process second chunk (cumulative streaming)
        self.service.process_streaming_chunk(chunk2)

        # Should have processed the complete cumulative update
        self.assertEqual(self.keyboard.output, "Hello world ")

    def test_reset_command_detection(self):
        """Test reset command detection in conversation text."""
        self.service.processor.reset({10: "Initial ", 20: "text "})
        
        # Send conversation with reset command
        test_xml = '<conversation>reset conversation</conversation><10>New </10><20>content </20>'
        
        with patch('builtins.print') as mock_print:
            self.service.process_xml_transcription(test_xml)
        
        # After reset, should have new content
        self.assertEqual(self.keyboard.output, "New content ")

    def test_streaming_reset_handling(self):
        """Test reset tag processing in streaming mode."""
        self.service.processor.reset({10: "Old ", 20: "text "})
        
        # Send reset separately then update
        self.service.process_streaming_chunk('<reset/>')
        self.service.process_streaming_chunk('<update><10>Fresh </10><20>start </20></update>')
        
        # Should only have new content after reset
        self.assertEqual(self.keyboard.output, "Fresh start ")

    def test_partial_update_streaming(self):
        """Test partial XML updates in streaming mode."""
        self.service.processor.reset({})
        
        # Simulate partial streaming
        self.service.process_streaming_chunk('<upda')
        self.service.process_streaming_chunk('te><10>Test</10></upd')
        self.service.process_streaming_chunk('ate>')
        
        # Should process when complete
        self.assertEqual(self.keyboard.output, "Test")

    def test_mixed_conversation_and_streaming(self):
        """Test mixed conversation tags and streaming updates."""
        self.service.processor.reset({})
        
        # First process conversation
        conv_xml = '<conversation>Starting dictation session</conversation>'
        with patch('builtins.print'):
            self.service.process_xml_transcription(conv_xml)
        
        # Then streaming updates
        stream_chunk = '<update><10>Streaming </10><20>text </20></update>'
        self.service.process_streaming_chunk(stream_chunk)
        
        self.assertEqual(self.keyboard.output, "Streaming text ")

    def test_end_stream_behavior(self):
        """Test end_stream behavior with remaining words."""
        initial_words = {10: "Hello ", 20: "there ", 30: "friend "}
        self.service.processor.reset(initial_words)
        
        # Update first word only
        self.service.processor.process_chunk("<10>Hi </10>")
        # Manually call end_stream to emit remaining
        self.service.processor.end_stream()
        
        # Incremental behavior: first update emits only word 10, end_stream flushes rest
        expected_operations = [
            ('bksp', 19),  # Backspace entire text (word 10 at position 0)
            ('emit', 'Hi '),  # Emit only word 10
            ('emit', 'there '),  # end_stream flushes word 20
            ('emit', 'friend ')  # end_stream flushes word 30
        ]
        self.assertEqual(self.keyboard.operations, expected_operations)
        self.assertEqual(self.keyboard.output, "Hi there friend ")


if __name__ == '__main__':
    unittest.main()