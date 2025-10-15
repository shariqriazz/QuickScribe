#!/usr/bin/env python3
"""
Test persistent state behavior across multiple transcriptions.
"""

import sys
import os
import unittest

# Add parent directory to path
parent_dir = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, parent_dir)
sys.path.append(os.path.join(parent_dir, 'lib', 'xml-stream'))

from transcription_service import TranscriptionService
from keyboard_injector import MockKeyboardInjector


class TestPersistentState(unittest.TestCase):
    """Test XMLStreamProcessor persistent state management."""
    
    def test_persistent_state_across_transcriptions(self):
        """Test that XMLStreamProcessor maintains state across multiple transcriptions."""
        class MockConfig:
            debug_enabled = False
            xml_stream_debug = False
        service = TranscriptionService(MockConfig())
        from keyboard_injector import MockKeyboardInjector
        keyboard = MockKeyboardInjector()
        service.keyboard = keyboard
        service.processor.keyboard = keyboard
        keyboard = service.keyboard
        
        # First transcription
        service.process_xml_transcription('<10>This is test </10><20>number one.</20>')
        first_output = keyboard.output
        self.assertEqual(first_output, "This is test number one. ")
        
        # Reset only streaming state (not processor state)
        service.reset_streaming_state()
        keyboard.reset()  # Clear output for clarity
        
        # Second transcription - should continue from ID 30
        service.process_xml_transcription('<30>This is test number two. </30><40>It should be appended </40><50>to the first.</50>')
        second_output = keyboard.output
        self.assertEqual(second_output, "This is test number two. It should be appended to the first. ")
        
        # Verify state persistence
        expected_words = {
            10: "This is test ",
            20: "number one. ",
            30: "This is test number two. ",
            40: "It should be appended ",
            50: "to the first. "
        }
        
        self.assertEqual(service.processor.current_words, expected_words)
        
        # Check context building
        xml_context = service._build_xml_from_processor()
        text_context = service._build_current_text()
        
        expected_xml = '<10>This is test </10><20>number one. </20><30>This is test number two. </30><40>It should be appended </40><50>to the first. </50>'
        expected_text = 'This is test number one. This is test number two. It should be appended to the first. '
        
        self.assertEqual(xml_context, expected_xml)
        self.assertEqual(text_context, expected_text)

    def test_explicit_reset_clears_state(self):
        """Test that explicit reset clears state."""
        class MockConfig:
            debug_enabled = False
            xml_stream_debug = False
        service = TranscriptionService(MockConfig())
        from keyboard_injector import MockKeyboardInjector
        keyboard = MockKeyboardInjector()
        service.keyboard = keyboard
        service.processor.keyboard = keyboard
        
        # Set up initial state
        service.process_xml_transcription('<10>Initial </10><20>content</20>')
        self.assertEqual(service.processor.current_words, {10: "Initial ", 20: "content "})
        
        # Explicit reset
        service.reset_all_state()
        self.assertEqual(service.processor.current_words, {})
        
        # New content should start from ID 10 again
        service.process_xml_transcription('<10>Fresh </10><20>start</20>')
        expected = {10: "Fresh ", 20: "start "}
        self.assertEqual(service.processor.current_words, expected)

    def test_streaming_state_reset_preserves_processor(self):
        """Test that streaming state reset doesn't affect processor state."""
        class MockConfig:
            debug_enabled = False
            xml_stream_debug = False
        service = TranscriptionService(MockConfig())
        from keyboard_injector import MockKeyboardInjector
        keyboard = MockKeyboardInjector()
        service.keyboard = keyboard
        service.processor.keyboard = keyboard
        
        # Set up state
        service.process_xml_transcription('<10>Preserved </10><20>state</20>')
        original_words = service.processor.current_words.copy()
        
        # Reset streaming state multiple times
        service.reset_streaming_state()
        service.reset_streaming_state()
        service.reset_streaming_state()
        
        # Processor state should be unchanged
        self.assertEqual(service.processor.current_words, original_words)

    def test_context_building_with_special_characters(self):
        """Test XML context building with characters that need escaping."""
        class MockConfig:
            debug_enabled = False
            xml_stream_debug = False
        service = TranscriptionService(MockConfig())
        from keyboard_injector import MockKeyboardInjector
        keyboard = MockKeyboardInjector()
        service.keyboard = keyboard
        service.processor.keyboard = keyboard
        
        # Process text with special XML characters
        service.process_xml_transcription('<10>AT&T </10><20>uses <brackets> </20><30>&amp; symbols</30>')
        
        xml_context = service._build_xml_from_processor()
        
        # Should have proper XML escaping - & symbol should be escaped once, not twice
        expected_xml = '<10>AT&amp;T </10><20>uses &lt;brackets&gt; </20><30>&amp; symbols </30>'
        self.assertEqual(xml_context, expected_xml)

    def test_sequential_id_continuation(self):
        """Test that word IDs continue sequentially across transcriptions."""
        class MockConfig:
            debug_enabled = False
            xml_stream_debug = False
        service = TranscriptionService(MockConfig())
        from keyboard_injector import MockKeyboardInjector
        keyboard = MockKeyboardInjector()
        service.keyboard = keyboard
        service.processor.keyboard = keyboard
        
        # First transcription
        service.process_xml_transcription('<10>First </10><20>batch</20>')
        service.reset_streaming_state()
        
        # Second transcription - IDs should continue
        service.process_xml_transcription('<30>Second </30><40>batch</40>')
        service.reset_streaming_state()
        
        # Third transcription - IDs should continue further
        service.process_xml_transcription('<50>Third </50><60>batch</60>')
        
        expected_words = {
            10: "First ",
            20: "batch ",
            30: "Second ",
            40: "batch ",
            50: "Third ",
            60: "batch "
        }
        
        self.assertEqual(service.processor.current_words, expected_words)

    def test_reset_command_detection_in_conversation(self):
        """Test that reset commands in conversation tags trigger state reset."""
        class MockConfig:
            debug_enabled = False
            xml_stream_debug = False
        service = TranscriptionService(MockConfig())
        from keyboard_injector import MockKeyboardInjector
        keyboard = MockKeyboardInjector()
        service.keyboard = keyboard
        service.processor.keyboard = keyboard
        
        # Set up initial state
        service.process_xml_transcription('<10>Initial </10><20>content</20>')
        self.assertNotEqual(service.processor.current_words, {})
        
        # Process conversation with reset command (should clear state)
        # The reset detection uses print(), not logging, so we'll just test the behavior
        service.process_xml_transcription('<conversation>reset conversation</conversation><10>New </10><20>content</20>')
        
        # State should be reset and contain new content only
        expected = {10: "New ", 20: "content "}
        self.assertEqual(service.processor.current_words, expected)


if __name__ == '__main__':
    unittest.main()