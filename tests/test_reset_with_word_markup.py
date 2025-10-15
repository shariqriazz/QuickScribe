#!/usr/bin/env python3
"""
Test reset tag embedded with word markup in the same XML chunk.
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


class TestResetWithWordMarkup(unittest.TestCase):
    """Test reset tag behavior when embedded with word markup."""

    def setUp(self):
        """Set up test environment."""
        class MockConfig:
            debug_enabled = True
            reset_state_each_response = False
            xml_stream_debug = False

        self.config = MockConfig()
        self.service = TranscriptionService(self.config)
        # Replace with MockKeyboardInjector for testing
        self.keyboard = MockKeyboardInjector()
        self.service.keyboard = self.keyboard
        self.service.processor.keyboard = self.keyboard

    def test_reset_followed_by_update(self):
        """Test that reset clears old content and new update replaces it completely."""
        # Set up initial state with some existing words
        initial_words = {
            10: "The ",
            20: "quick ",
            30: "brown ",
            40: "fox ",
            50: "jumps "
        }
        self.service.processor.reset(initial_words)

        # Verify initial state is set
        self.assertEqual(self.service.processor.current_words, initial_words)

        # Send XML with reset followed by new word updates wrapped in update tags
        xml_with_reset = '<reset/><update><100>Fresh </100><110>new </110><120>content </120><130>here.</130></update>'

        # Process the XML
        self.service.process_xml_transcription(xml_with_reset)

        # Assert all old sequences are completely gone from processor state
        for old_seq in initial_words.keys():
            self.assertNotIn(old_seq, self.service.processor.current_words,
                           f"Old sequence {old_seq} should be removed after reset")

        # Assert old content is not in the output
        self.assertNotIn("The", self.keyboard.output)
        self.assertNotIn("quick", self.keyboard.output)
        self.assertNotIn("brown", self.keyboard.output)
        self.assertNotIn("fox", self.keyboard.output)
        self.assertNotIn("jumps", self.keyboard.output)

        # Verify new content exists in the output
        self.assertEqual(self.keyboard.output, "Fresh new content here. ")

        # Verify new words are in the processor state
        self.assertIn(100, self.service.processor.current_words)
        self.assertIn(110, self.service.processor.current_words)
        self.assertIn(120, self.service.processor.current_words)
        self.assertIn(130, self.service.processor.current_words)

        # Verify exact state - should only have the new words
        self.assertEqual(len(self.service.processor.current_words), 4,
                        "Should only have 4 new words after reset")

        self.assertEqual(self.service.processor.current_words[100], "Fresh ")
        self.assertEqual(self.service.processor.current_words[110], "new ")
        self.assertEqual(self.service.processor.current_words[120], "content ")
        self.assertEqual(self.service.processor.current_words[130], "here. ")


if __name__ == '__main__':
    unittest.main(verbosity=2)