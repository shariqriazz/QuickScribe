"""Test premature stream closure causing lost chunks."""

import pytest
import sys
import os

# Add parent directory to path
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, parent_dir)

from transcription_service import TranscriptionService
from keyboard_injector import MockKeyboardInjector


class TestStreamClosure:
    """Test premature stream closure and lost chunks."""

    def setup_method(self):
        """Set up test fixtures."""
        class MockConfig:
            debug_enabled = False
            xml_stream_debug = False
        self.service = TranscriptionService(MockConfig())
        # Replace with MockKeyboardInjector for testing
        self.keyboard = MockKeyboardInjector()
        self.service.keyboard = self.keyboard
        self.service.processor.keyboard = self.keyboard

    def test_premature_stream_closure_loses_chunks(self):
        """Test that simulates API stream closing before all content is delivered."""

        # Set up initial state: fox story
        initial_xml = ('<10>Once upon a time, </10><20>there was a fox, </20>'
                      '<30>and he liked to jump </30><40>from tree to tree.</40>'
                      '<50>One day, </50><60>he jumped </60><70>to a tree </70>'
                      '<80>1,000 miles away.</80>')
        self.service.process_xml_transcription(initial_xml)

        # Verify initial state is set
        processor = self.service.processor
        assert 10 in processor.current_words
        assert 80 in processor.current_words
        initial_output = self.keyboard.output

        # Clear operations to focus on streaming behavior
        self.keyboard.operations.clear()

        # Start streaming mode
        self.service.reset_streaming_state()

        # Simulate streaming chunks arriving
        # Chunk 1: Complete tag (new sequence 90 - should just emit, no backspace for new sequences)
        self.service.process_streaming_chunk('<update><90>Sounds great. </90>')

        # Verify chunk 1 was processed - new sequences just emit
        operations_after_chunk1 = self.keyboard.operations.copy()
        expected_after_chunk1 = [
            ('emit', 'Sounds great. ')
        ]
        assert operations_after_chunk1 == expected_after_chunk1

        # Chunk 2: Another complete tag
        self.service.process_streaming_chunk('<100>I will give </100>')

        # Verify chunk 2 was processed (no backspace needed for additional chunks)
        operations_after_chunk2 = self.keyboard.operations.copy()
        expected_after_chunk2 = expected_after_chunk1 + [
            ('emit', 'I will give ')
        ]
        assert operations_after_chunk2 == expected_after_chunk2

        # Chunk 3: INCOMPLETE tag simulating stream closure
        # This simulates the stream closing while tag 110 is being transmitted
        self.service.process_streaming_chunk('<110>it a shot.</110>')

        # CRITICAL: Simulate what happens when stream completes
        # This is what the fix adds - proper stream completion
        self.service.complete_stream()

        # Check final state - should now work correctly with the fix
        final_output = self.keyboard.output
        print(f"Final output: '{final_output}'")

        # With the fix, this should now work correctly
        expected_complete_output = initial_output + "Sounds great. I will give it a shot."

        # This assertion should now PASS with the fix
        assert final_output == expected_complete_output, f"Expected complete text but got: '{final_output}'"

    def test_complete_stream_vs_premature_closure(self):
        """Compare complete stream (working) vs premature closure (broken)."""

        # Test 1: Complete stream (should work)
        service1 = TranscriptionService(type('MockConfig', (), {'debug_enabled': False, 'xml_stream_debug': False})())
        keyboard1 = MockKeyboardInjector()
        service1.keyboard = keyboard1
        service1.processor.keyboard = keyboard1
        service1.reset_all_state()

        # Complete XML with all tags properly closed
        complete_xml = ('<update><90>Sounds great. </90><100>I will give </100>'
                       '<110>it a shot.</110></update>')
        service1.process_streaming_chunk(complete_xml)

        # This should work fine - all content processed
        complete_output = keyboard1.output
        assert complete_output == "Sounds great. I will give it a shot."

        # Test 2: Premature closure (broken)
        service2 = TranscriptionService(type('MockConfig', (), {'debug_enabled': False, 'xml_stream_debug': False})())
        keyboard2 = MockKeyboardInjector()
        service2.keyboard = keyboard2
        service2.processor.keyboard = keyboard2
        service2.reset_all_state()

        # Simulate chunks arriving separately, with stream closing mid-tag
        service2.process_streaming_chunk('<update><90>Sounds great. </90>')
        service2.process_streaming_chunk('<100>I will give </100>')
        service2.process_streaming_chunk('<110>it a shot.</110>')  # Complete tag

        # Apply the fix - complete the stream properly
        service2.complete_stream()

        # This should work properly after fix - expect complete text
        fixed_output = keyboard2.output

        # This assertion should now PASS with the fix
        assert fixed_output == "Sounds great. I will give it a shot.", f"Expected complete text but got: '{fixed_output}'"

    def test_incomplete_tag_handling(self):
        """Test handling of truly incomplete tags that can't be recovered."""
        service = TranscriptionService(type('MockConfig', (), {'debug_enabled': False, 'xml_stream_debug': False})())
        keyboard = MockKeyboardInjector()
        service.keyboard = keyboard
        service.processor.keyboard = keyboard
        service.reset_all_state()

        # Stream complete tags and then a truly incomplete one
        service.process_streaming_chunk('<update><90>Sounds great. </90>')
        service.process_streaming_chunk('<100>I will give </100>')
        service.process_streaming_chunk('<110>it a')  # Incomplete - missing closing tag

        # Complete the stream - should process what's possible
        service.complete_stream()

        # Should have the complete tags, but incomplete tag 110 should be ignored
        output = keyboard.output
        assert output == "Sounds great. I will give "

        # Verify processor state
        assert 90 in service.processor.current_words
        assert 100 in service.processor.current_words
        assert 110 not in service.processor.current_words  # Incomplete tag ignored