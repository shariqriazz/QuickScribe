"""Test case that reproduces the streaming progression bug exactly as described in the trace."""

import unittest
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'lib', 'xml-stream'))
from xml_stream_processor import XMLStreamProcessor
from keyboard_injector import MockKeyboardInjector


class TestStreamingProgressionBug(unittest.TestCase):
    """Test the exact progression that causes the streaming bug."""

    def setUp(self):
        """Set up test with a single processor instance."""
        self.keyboard = MockKeyboardInjector()
        self.processor = XMLStreamProcessor(self.keyboard)

    def test_streaming_progression_incremental(self):
        """Test the correct incremental streaming behavior."""

        print("\n=== STEP 1: Initial transcription (incremental) ===")

        # Step 1: Process initial transcription with incremental emission
        fragments_1 = [
            '<10>Once upon a time, </10>',    # Should emit "Once upon a time, " immediately
            '<20>there was a squirrel, </20>', # Should emit "there was a squirrel, "
            '<30>and he liked to jump </30>',  # Should emit "and he liked to jump "
            '<40>from tree to tree.</40>'      # Should emit "from tree to tree."
        ]

        # Process each fragment and check incremental output
        self.processor.process_chunk(fragments_1[0])
        self.assertEqual(self.keyboard.output, "Once upon a time, ", "After first fragment")

        self.processor.process_chunk(fragments_1[1])
        self.assertEqual(self.keyboard.output, "Once upon a time, there was a squirrel, ", "After second fragment")

        self.processor.process_chunk(fragments_1[2])
        self.assertEqual(self.keyboard.output, "Once upon a time, there was a squirrel, and he liked to jump ", "After third fragment")

        self.processor.process_chunk(fragments_1[3])
        expected_after_fourth = "Once upon a time, there was a squirrel, and he liked to jump from tree to tree."
        self.assertEqual(self.keyboard.output, expected_after_fourth, "After fourth fragment")

        # end_stream adds trailing space for xdotool compatibility
        self.processor.end_stream()
        self.assertEqual(self.keyboard.output, expected_after_fourth + " ", "After end_stream step 1")

        print("\n=== STEP 2: Add more content (incremental) ===")

        # Step 2: Add more content incrementally
        self.processor.process_chunk('<50>One day, </50>')
        expected_after_50 = expected_after_fourth + " One day, "
        self.assertEqual(self.keyboard.output, expected_after_50, "After chunk 50")

        self.processor.process_chunk('<60>he jumped to a tree </60>')
        expected_after_60 = expected_after_50 + "he jumped to a tree "
        self.assertEqual(self.keyboard.output, expected_after_60, "After chunk 60")

        self.processor.process_chunk('<70>that was 1000 miles away.</70>')
        expected_after_70 = expected_after_60 + "that was 1000 miles away."
        self.assertEqual(self.keyboard.output, expected_after_70, "After chunk 70")

        self.processor.end_stream()
        self.assertEqual(self.keyboard.output, expected_after_70 + " ", "After end_stream step 2")

        print("\n=== STEP 3: Modify beginning (incremental behavior) ===")

        # Step 3: Change "Once upon a time, " to "One day, " - should show proper incremental behavior
        self.processor.process_chunk('<10>One day, </10>')

        # After processing chunk 10, should have:
        # - Backspaced entire text
        # - Emitted "One day, " (only chunk 10)
        # - WAIT for more chunks or end_stream
        self.assertEqual(self.keyboard.output, "One day, ", "After modifying chunk 10 - should only emit chunk 10")

        # end_stream should flush remaining chunks 20-70 and add trailing space
        self.processor.end_stream()
        expected_final = "One day, there was a squirrel, and he liked to jump from tree to tree. One day, he jumped to a tree that was 1000 miles away. "
        self.assertEqual(self.keyboard.output, expected_final, "After end_stream - should flush remaining chunks")

        print(f"SUCCESS: Incremental behavior works correctly!")
        print(f"Final output: '{self.keyboard.output}'")


if __name__ == '__main__':
    unittest.main(verbosity=2)