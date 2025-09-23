"""Integration tests for the complete dictation workflow."""

import unittest
from unittest.mock import Mock, patch

from lib.word_stream import WordStreamParser, DictationWord
from lib.diff_engine import DiffEngine, DiffResult
from lib.output_manager import OutputManager


class TestDictationIntegration(unittest.TestCase):
    """Test complete dictation pipeline integration."""
    
    def setUp(self):
        """Set up test environment."""
        self.word_parser = WordStreamParser()
        self.diff_engine = DiffEngine()
        self.output_manager = Mock(spec=OutputManager)
        self.current_words = []

    def assert_output_called_with(self, backspaces: int, text: str):
        """Helper to verify output manager calls."""
        self.output_manager.execute_diff.assert_called_with(
            DiffResult(backspaces=backspaces, new_text=text)
        )

    def test_single_word_flow(self):
        """Test transcription of a single complete word."""
        # Simulate partial word arrival
        words = self.word_parser.parse("<1>he")
        self.assertEqual(len(words), 0)
        self.assertEqual(self.word_parser.get_buffer(), "<1>he")
        
        # Complete the word
        words = self.word_parser.parse("llo</1>")
        self.current_words = words
        
        self.assertEqual(len(words), 1)
        self.assertEqual(words[0].text, "hello")
        self.assertEqual(words[0].id, 1)

    def test_multi_word_transcription(self):
        """Test transcription of multiple words."""
        # Start with first word
        old_words = [DictationWord(id=1, text="hello")]
        self.current_words = old_words

        # Add second word
        new_words = [
            DictationWord(id=1, text="hello"),
            DictationWord(id=2, text="world")
        ]
        diff = self.diff_engine.compare(old_words, new_words)
        self.output_manager.execute_diff(diff)
        self.current_words = new_words

        # Should add " world" (with leading space)
        self.assert_output_called_with(backspaces=0, text=" world")
        self.assertEqual(len(self.current_words), 2)
        self.assertEqual(self.current_words[1].text, "world")

    def test_word_correction(self):
        """Test correction of previously transcribed words."""
        # Initial words
        old_words = [
            DictationWord(id=1, text="hello"),
            DictationWord(id=2, text="word")
        ]
        self.current_words = old_words

        # Correct second word
        new_words = [
            DictationWord(id=1, text="hello"),
            DictationWord(id=2, text="world")
        ]
        diff = self.diff_engine.compare(old_words, new_words)
        self.output_manager.execute_diff(diff)
        self.current_words = new_words

        # Should backspace " word" (5 chars) and type " world"
        self.assert_output_called_with(backspaces=5, text=" world")
        self.assertEqual(self.current_words[1].text, "world")

    def test_mixed_updates(self):
        """Test mix of corrections and additions."""
        # Initial state
        old_words = [
            DictationWord(id=1, text="hello"),
            DictationWord(id=2, text="beautiful")
        ]
        self.current_words = old_words

        # Correct first word and add new word
        new_words = [
            DictationWord(id=1, text="hi"),
            DictationWord(id=2, text="beautiful"),
            DictationWord(id=3, text="world")
        ]
        diff = self.diff_engine.compare(old_words, new_words)
        self.output_manager.execute_diff(diff)
        self.current_words = new_words

        # Should backspace "hello beautiful" (15 chars) and type "hi beautiful world"
        self.assert_output_called_with(backspaces=15, text="hi beautiful world")
        self.assertEqual(len(self.current_words), 3)
        self.assertEqual([w.text for w in self.current_words], 
                        ["hi", "beautiful", "world"])

    def test_state_reset(self):
        """Test state reset on completion marker."""
        # Initial state
        self.word_parser.parse("<1>hello</1>")
        self.current_words = [DictationWord(id=1, text="hello")]
        
        # Simulate completion
        self.word_parser.clear_buffer()
        self.current_words = []
        
        self.assertEqual(len(self.current_words), 0)
        self.assertEqual(self.word_parser.get_buffer(), "")

    def test_partial_word_updates(self):
        """Test handling of partial word updates."""
        # Start word
        words = self.word_parser.parse("<1>th")
        self.assertEqual(self.word_parser.get_buffer(), "<1>th")
        
        # Update partial
        words = self.word_parser.parse("ere")
        self.assertEqual(self.word_parser.get_buffer(), "<1>there")
        
        # Complete word
        words = self.word_parser.parse("</1>")
        self.current_words = words
        
        self.assertEqual(len(words), 1)
        self.assertEqual(words[0].text, "there")

    def test_consecutive_xml_tags_spacing(self):
        """Test that consecutive XML tags produce properly spaced output."""
        # Simulate receiving consecutive XML tags (the reported issue)
        xml_input = "<10>This</10><20>is</20><30>a</30><40>dictation</40><50>test</50>"

        # Parse the XML to extract words
        words = self.word_parser.parse(xml_input)

        # Verify we got the expected words
        self.assertEqual(len(words), 5)
        expected_texts = ["This", "is", "a", "dictation", "test"]
        for i, expected_text in enumerate(expected_texts):
            self.assertEqual(words[i].text, expected_text)

        # Simulate the diff engine creating output text (from empty to these words)
        diff_result = self.diff_engine.compare([], words)

        # The output should be properly spaced, NOT "Thisisadictationtest"
        self.assertEqual(diff_result.new_text, "This is a dictation test")
        self.assertEqual(diff_result.backspaces, 0)


if __name__ == '__main__':
    unittest.main()