"""Test XML parser behavior with mismatched opening/closing tags."""

import sys
import io
import os
import unittest

# Add parent directory to path for imports
parent_dir = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, parent_dir)

from xml_stream_processor import XMLStreamProcessor
from keyboard_injector import MockKeyboardInjector


class TestMismatchedTags(unittest.TestCase):

    def setUp(self):
        """Set up test fixtures."""
        self.keyboard = MockKeyboardInjector()
        self.processor = XMLStreamProcessor(self.keyboard, debug_enabled=False)

    def test_mismatched_tag_accepted_with_warning(self):
        """Mismatched tags should be accepted and use opening tag number."""
        # Capture stderr to check for warning
        captured_stderr = io.StringIO()
        old_stderr = sys.stderr
        sys.stderr = captured_stderr

        try:
            # Mismatched tags: opens 20, closes 25
            self.processor.reset({})
            self.processor.process_chunk('<10>Update the post-write guidance </10><20>to indicate </25>')
            self.processor.end_stream()

            # Should process both tags despite mismatch
            self.assertEqual(self.keyboard.output, "Update the post-write guidance to indicate ")

            # Check for warning in stderr
            stderr_output = captured_stderr.getvalue()
            self.assertIn("XML tag mismatch", stderr_output)
            self.assertIn("<20>...</25>", stderr_output)
            self.assertIn("using opening tag 20", stderr_output)
        finally:
            sys.stderr = old_stderr

    def test_multiple_mismatched_tags(self):
        """Multiple mismatched tags should all be accepted."""
        captured_stderr = io.StringIO()
        old_stderr = sys.stderr
        sys.stderr = captured_stderr

        try:
            self.processor.reset({})
            self.processor.process_chunk('<10>First </15><20>second </30><40>third </40>')
            self.processor.end_stream()

            # All content should be emitted
            self.assertEqual(self.keyboard.output, "First second third ")

            # Check warnings for both mismatches
            stderr_output = captured_stderr.getvalue()
            self.assertIn("<10>...</15>", stderr_output)
            self.assertIn("<20>...</30>", stderr_output)
            # Tag 40 should not generate warning (matches)
            self.assertNotIn("<40>...</40>", stderr_output)
        finally:
            sys.stderr = old_stderr

    def test_sequence_uses_opening_tag_number(self):
        """Processor should use opening tag number for sequence ordering."""
        self.processor.reset({})
        # Send out of order with mismatched closing tags
        self.processor.process_chunk('<30>third </35><10>first </15><20>second </25>')
        self.processor.end_stream()

        # Should emit in sequence order: 10, 20, 30
        self.assertEqual(self.keyboard.output, "first second third ")

    def test_mismatched_tag_updates_existing_sequence(self):
        """Mismatched tags should update using opening tag number."""
        captured_stderr = io.StringIO()
        old_stderr = sys.stderr
        sys.stderr = captured_stderr

        try:
            self.processor.reset({10: "old ", 20: "text "})
            # Update sequence 10 with mismatched closing tag
            self.processor.process_chunk('<10>new </15>')
            self.processor.end_stream()

            # Should update sequence 10
            self.assertEqual(self.keyboard.output, "new text ")
        finally:
            sys.stderr = old_stderr


if __name__ == '__main__':
    unittest.main()
