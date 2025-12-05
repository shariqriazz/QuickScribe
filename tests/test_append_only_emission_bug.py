"""
Test to demonstrate that append-only content (new tags without changes)
is not emitted by XMLStreamProcessor.
"""
import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib', 'xml-stream'))

from xml_stream_processor import XMLStreamProcessor
from keyboard_injector import MockKeyboardInjector


class TestAppendOnlyEmissionBug(unittest.TestCase):
    """Test that proves append-only content fails to emit."""

    def setUp(self):
        self.keyboard = MockKeyboardInjector()
        self.processor = XMLStreamProcessor(self.keyboard)

    def test_append_only_content_not_emitted(self):
        """
        Demonstrate that appending new tags without changing existing ones
        results in content never being emitted to keyboard.

        This test SHOULD FAIL to prove the bug exists.
        """
        # Step 1: Process initial content (will trigger backspace and emission)
        print("\n=== STEP 1: Initial content (should emit) ===")
        self.processor.reset({})
        self.processor.process_chunk('<10>Hello </10><20>world</20>')
        self.processor.end_stream()

        initial_output = self.keyboard.output
        print(f"Initial output: '{initial_output}'")
        self.assertEqual(initial_output, "Hello world ", "Initial content should be emitted")

        # Verify processor state
        print(f"Current words: {self.processor.current_words}")
        print(f"Last emitted seq: {self.processor.last_emitted_seq}")
        print(f"Backspace performed: {self.processor.backspace_performed}")

        # Step 2: Clear keyboard output to track new emissions
        print("\n=== STEP 2: Append new content (should emit but doesn't) ===")
        self.keyboard.output = ""

        # Step 3: Append new content without changing existing
        # This is pure append - no changes to existing tags 10 or 20
        self.processor.process_chunk('<30>How </30><40>are </40><50>you?</50>')

        # Check state before end_stream
        print(f"Current words after append: {self.processor.current_words}")
        print(f"Last emitted seq after append: {self.processor.last_emitted_seq}")
        print(f"Backspace performed after append: {self.processor.backspace_performed}")

        # Step 4: Call end_stream to flush
        self.processor.end_stream()

        append_output = self.keyboard.output
        print(f"Output after append: '{append_output}'")

        # Step 5: This assertion SHOULD FAIL if the bug exists
        # We expect "How are you?" but likely get ""
        expected_append = "How are you?"

        # BUILD FULL STRING to verify internal state is correct
        full_text = self.processor._build_string_from_words(self.processor.current_words)
        print(f"Full internal text: '{full_text}'")
        self.assertEqual(full_text, "Hello world How are you? ", "Internal state should have all content")

        # THIS ASSERTION SHOULD FAIL - proving the bug
        self.assertEqual(
            append_output,
            expected_append + " ",
            f"BUG DETECTED: Appended content not emitted! Expected '{expected_append} ' but got '{append_output}'"
        )


if __name__ == '__main__':
    unittest.main(verbosity=2)