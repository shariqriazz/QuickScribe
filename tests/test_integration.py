"""Integration tests for XMLStreamProcessor-based dictation workflow."""

import unittest
from unittest.mock import Mock, patch
import sys
import os

# Add parent directory to path
parent_dir = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, parent_dir)
sys.path.append(os.path.join(parent_dir, 'lib', 'xml-stream'))

from xml_stream_processor import XMLStreamProcessor
from keyboard_injector import MockKeyboardInjector
from transcription_service import TranscriptionService


class TestXMLStreamIntegration(unittest.TestCase):
    """Test complete dictation pipeline integration using XMLStreamProcessor."""
    
    def setUp(self):
        """Set up test environment."""
        self.keyboard = MockKeyboardInjector()
        self.processor = XMLStreamProcessor(self.keyboard)
        self.transcription_service = TranscriptionService(use_xdotool=False)

    def test_single_word_processing(self):
        """Test transcription of a single complete word."""
        initial_words = {}
        self.processor.reset(initial_words)
        
        # Process single word
        self.processor.process_chunk("<10>hello </10>")
        self.processor.end_stream()
        
        # Verify output
        self.assertEqual(self.keyboard.output, "hello ")
        self.assertEqual(len(self.keyboard.operations), 1)
        self.assertEqual(self.keyboard.operations[0], ('emit', 'hello '))

    def test_multi_word_transcription(self):
        """Test transcription of multiple words."""
        initial_words = {10: "hello "}
        self.processor.reset(initial_words)
        
        # Add second word - XMLStreamProcessor emits words in sequence without backspacing when adding
        self.processor.process_chunk("<20>world </20>")
        self.processor.end_stream()
        
        # XMLStreamProcessor just emits the new word since it's sequential
        expected_operations = [('emit', 'world ')]
        self.assertEqual(self.keyboard.operations, expected_operations)
        self.assertEqual(self.keyboard.output, "world ")

    def test_word_correction(self):
        """Test correction of previously transcribed words."""
        initial_words = {10: "hello ", 20: "word "}
        self.processor.reset(initial_words)
        
        # Set up keyboard to simulate existing text
        self.keyboard.output = "hello word "
        self.keyboard.operations = []
        
        # Correct second word
        self.processor.process_chunk("<20>world </20>")
        self.processor.end_stream()
        
        # XMLStreamProcessor calculates backspace from common prefix
        # Original: "hello word " vs Modified: "hello world " -> backspace 2 chars ("d "), emit "world "
        expected_operations = [
            ('bksp', 2),  # backspace "d " from "word " 
            ('emit', 'world ')
        ]
        self.assertEqual(self.keyboard.operations, expected_operations)
        # After backspacing 2 chars from end: "hello word " -> "hello wor" -> "hello worworld "
        self.assertEqual(self.keyboard.output, "hello worworld ")

    def test_gap_filling(self):
        """Test gap filling between non-consecutive updates."""
        initial_words = {10: "The ", 20: "quick ", 30: "brown ", 40: "fox "}
        self.processor.reset(initial_words)
        
        # Update non-consecutive words
        self.processor.process_chunk("<20>fast </20>")
        self.processor.process_chunk("<40>dog </40>")
        self.processor.end_stream()
        
        # Should backspace to "The " then emit rest
        expected_operations = [
            ('bksp', 16),  # len("The quick brown fox ") - len("The ")
            ('emit', 'fast '),
            ('emit', 'brown '),  # Gap fill
            ('emit', 'dog ')
        ]
        self.assertEqual(self.keyboard.operations, expected_operations)
        self.assertEqual(self.keyboard.output, "fast brown dog ")

    def test_word_deletion(self):
        """Test empty word updates delete from state."""
        initial_words = {10: "The ", 20: "quick ", 30: "brown "}
        self.processor.reset(initial_words)
        
        # Delete middle word
        self.processor.process_chunk("<20></20>")
        self.processor.end_stream()
        
        # Should emit remaining words
        expected_operations = [
            ('bksp', 12),  # len("The quick brown ") - len("The ")
            ('emit', 'brown ')
        ]
        self.assertEqual(self.keyboard.operations, expected_operations)
        self.assertEqual(self.keyboard.output, 'brown ')

    def test_xml_fragmentation(self):
        """Test XML tags split across multiple chunks."""
        initial_words = {10: "Hi "}
        self.processor.reset(initial_words)
        
        # Fragment the XML tag across chunks
        self.processor.process_chunk("<1")
        self.processor.process_chunk("0>Bye ")
        self.processor.process_chunk("</1")
        self.processor.process_chunk("0>")
        
        expected_operations = [
            ('bksp', 3),  # len("Hi ") - len("")
            ('emit', "Bye ")
        ]
        self.assertEqual(self.keyboard.operations, expected_operations)
        self.assertEqual(self.keyboard.output, "Bye ")

    def test_transcription_service_integration(self):
        """Test TranscriptionService with XMLStreamProcessor."""
        # Create transcription service with mock keyboard
        service = TranscriptionService(use_xdotool=False)
        
        # Mock the processor to use our test keyboard
        service.keyboard = self.keyboard
        service.processor = XMLStreamProcessor(self.keyboard)
        service.processor.reset({})
        
        # Test streaming chunk processing
        chunk_with_update = '<update><10>Hello </10><20>world </20></update>'
        service.process_streaming_chunk(chunk_with_update)
        
        # Verify words were processed
        self.assertEqual(self.keyboard.output, "Hello world ")

    def test_reset_handling(self):
        """Test reset tag processing in transcription service."""
        service = TranscriptionService(use_xdotool=False)
        service.keyboard = self.keyboard
        service.processor = XMLStreamProcessor(self.keyboard)
        
        # Start with some words
        service.processor.reset({10: "Hello "})
        
        # Process a reset - this should clear the processor but not emit anything yet
        service.process_streaming_chunk('<reset/>')
        # Then process an update
        service.process_streaming_chunk('<update><10>Goodbye </10></update>')
        
        # Should only have new word after reset
        self.assertEqual(self.keyboard.output, "Goodbye ")

    def test_conversation_tag_processing(self):
        """Test conversation tags are processed correctly."""
        service = TranscriptionService(use_xdotool=False)
        service.keyboard = self.keyboard  
        service.processor = XMLStreamProcessor(self.keyboard)
        service.processor.reset({})
        
        # Test XML with conversation and word tags
        test_xml = '<conversation>AI response here</conversation><10>hello </10><20>world </20>'
        
        with patch('builtins.print') as mock_print:
            service.process_xml_transcription(test_xml)
            
            # Verify conversation was printed
            mock_print.assert_called()
            
            # Verify words were processed
            self.assertEqual(self.keyboard.output, "hello world ")

    def test_empty_initial_state(self):
        """Test processor with empty initial word mapping."""
        self.processor.reset({})
        
        self.processor.process_chunk("<10>Hello </10>")
        self.processor.end_stream()
        
        # No backspace needed with empty initial state
        expected_operations = [('emit', "Hello ")]
        self.assertEqual(self.keyboard.operations, expected_operations)
        self.assertEqual(self.keyboard.output, "Hello ")

    def test_multiple_tags_single_chunk(self):
        """Test multiple complete tags in one chunk."""
        initial_words = {10: "The ", 20: "quick ", 30: "brown "}
        self.processor.reset(initial_words)
        
        # Multiple complete tags
        self.processor.process_chunk("<10>A </10><20>fast </20>")
        self.processor.end_stream()
        
        expected_operations = [
            ('bksp', 16),  # len("The quick brown ") - len("")
            ('emit', "A "),
            ('emit', "fast "),
            ('emit', "brown ")  # End stream emits remaining
        ]
        self.assertEqual(self.keyboard.operations, expected_operations)
        self.assertEqual(self.keyboard.output, "A fast brown ")


if __name__ == '__main__':
    unittest.main()