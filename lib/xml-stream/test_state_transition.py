"""Test state transitions in XML Stream Processor."""

import pytest
import sys
import os

# Add parent directory to path
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, parent_dir)

from transcription_service import TranscriptionService
from keyboard_injector import MockKeyboardInjector


class TestXMLStateTransition:
    """Test complex state transitions in XMLStreamProcessor via TranscriptionService."""

    def setup_method(self):
        """Set up test fixtures."""
        class MockConfig:
            use_xdotool = False
            debug_enabled = False
        self.service = TranscriptionService(MockConfig())
        self.keyboard = self.service.keyboard

    def test_integration_state_transition_via_xml_transcription(self):
        """Integration test: fake initial state, reset, real initial state, new sequences."""

        # First operation: provide fake initial state via XML transcription
        self.service.process_xml_transcription('<1>Fake </1><2>initial </2><3>content</3>')

        # Validate stage 1: fake initial state processed
        expected_stage1 = [
            ('emit', "Fake "),
            ('emit', "initial "),
            ('emit', "content")
        ]
        assert self.keyboard.operations == expected_stage1
        assert self.keyboard.output == "Fake initial content"
        processor = self.service.processor
        assert 1 in processor.current_words
        assert 2 in processor.current_words
        assert 3 in processor.current_words

        # Second operation: reset via XML transcription
        self.service.process_xml_transcription('<reset/>')

        # Validate stage 2: reset cleared state, no new operations
        assert self.keyboard.operations == expected_stage1  # No new operations added
        assert self.keyboard.output == "Fake initial content"  # Output unchanged
        assert len(processor.current_words) == 0  # State was reset

        # Third operation: "once upon a time" initial state via XML transcription
        self.service.process_xml_transcription('<10>Once upon a time, </10><20>there was a fox, </20><30>and he liked to jump </30><40>from tree to tree.</40><50>One day, </50><60>he jumped </60><70>to a tree </70><80>1,000 miles away.</80>')

        # Validate stage 3: initial story state processed
        expected_stage3 = expected_stage1 + [
            ('emit', "Once upon a time, "),
            ('emit', "there was a fox, "),
            ('emit', "and he liked to jump "),
            ('emit', "from tree to tree."),
            ('emit', "One day, "),
            ('emit', "he jumped "),
            ('emit', "to a tree "),
            ('emit', "1,000 miles away.")
        ]
        assert self.keyboard.operations == expected_stage3
        assert self.keyboard.output == "Fake initial contentOnce upon a time, there was a fox, and he liked to jump from tree to tree.One day, he jumped to a tree 1,000 miles away."
        assert 10 in processor.current_words
        assert 80 in processor.current_words

        # Fourth operation: "sounds great" new sequences via XML transcription
        self.service.process_xml_transcription('<90>Sounds great. </90><100>I will give </100><110>it a shot.</110>')

        # Validate final stage: new sequences processed without backspace
        expected_final = expected_stage3 + [
            ('emit', "Sounds great. "),
            ('emit', "I will give "),
            ('emit', "it a shot.")
        ]
        assert self.keyboard.operations == expected_final
        assert self.keyboard.output == "Fake initial contentOnce upon a time, there was a fox, and he liked to jump from tree to tree.One day, he jumped to a tree 1,000 miles away.Sounds great. I will give it a shot."

        # Verify final internal state - both old and new sequences coexist
        assert 10 in processor.current_words
        assert 80 in processor.current_words
        assert 90 in processor.current_words
        assert 100 in processor.current_words
        assert 110 in processor.current_words
        assert processor.current_words[90] == "Sounds great. "
        assert processor.current_words[100] == "I will give "
        assert processor.current_words[110] == "it a shot."

    def test_incremental_paragraph_replacement(self):
        """Test incremental replacement of a paragraph."""
        # Initial state: a paragraph with multiple chunks
        initial_words = {
            10: "Once upon a time, ",
            20: "there was a fox, ",
            30: "and he liked to jump ",
            40: "from tree to tree.",
            50: "One day, ",
            60: "he jumped ",
            70: "to a tree ",
            80: "1,000 miles away."
        }
        self.service.processor.reset(initial_words)

        # Emit the initial content to the keyboard first
        for seq in sorted(initial_words.keys()):
            self.keyboard.emit(initial_words[seq])

        # Clear operations to focus on the replacement behavior
        self.keyboard.operations.clear()

        # Start streaming mode for incremental processing
        self.service.processor.start_stream()

        # Incrementally process new state chunk by chunk
        self.service.processor.process_chunk("<90>Sounds great. </90>")
        # Should backspace all content and emit first chunk
        expected_after_first = [
            ('bksp', 120),  # Length of the entire original text
            ('emit', "Sounds great. ")
        ]
        assert self.keyboard.operations == expected_after_first

        # Process second chunk
        self.service.processor.process_chunk("<100>I will give </100>")
        # Should emit second chunk (no backspace needed)
        expected_after_second = expected_after_first + [
            ('emit', "I will give ")
        ]
        assert self.keyboard.operations == expected_after_second

        # Process third chunk and end stream
        self.service.processor.process_chunk("<110>it a shot.</110>")
        self.service.processor.end_stream()
        # Should emit third chunk
        expected_final = expected_after_second + [
            ('emit', "it a shot.")
        ]
        assert self.keyboard.operations == expected_final
        assert self.keyboard.output == "Sounds great. I will give it a shot."