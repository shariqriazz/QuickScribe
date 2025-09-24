"""
Test module for the diff_engine module.
"""

import unittest
from lib.word_stream import DictationWord
from lib.diff_engine import DiffEngine, DiffResult


class TestDiffEngine(unittest.TestCase):
    def setUp(self):
        self.engine = DiffEngine()

    def test_empty_lists(self):
        """Test comparison of empty lists."""
        result = self.engine.compare([], [])
        self.assertEqual(result, DiffResult(backspaces=0, new_text=""))

    def test_identical_lists(self):
        """Test comparison of identical lists."""
        words = [
            DictationWord(id=1, text="hello"),
            DictationWord(id=2, text="world")
        ]
        result = self.engine.compare(words, words)
        self.assertEqual(result, DiffResult(backspaces=0, new_text=""))

    def test_simple_append(self):
        """Test appending new words."""
        old_words = [
            DictationWord(id=1, text="hello "),
            DictationWord(id=2, text="world")
        ]
        new_words = [
            DictationWord(id=1, text="hello "),
            DictationWord(id=2, text="world"),
            DictationWord(id=3, text=" test")
        ]
        result = self.engine.compare(old_words, new_words)
        self.assertEqual(result, DiffResult(backspaces=0, new_text=" test"))

    def test_simple_deletion(self):
        """Test deleting words from the end."""
        old_words = [
            DictationWord(id=1, text="hello "),
            DictationWord(id=2, text="world "),
            DictationWord(id=3, text="test")
        ]
        new_words = [
            DictationWord(id=1, text="hello "),
            DictationWord(id=2, text="world ")
        ]
        result = self.engine.compare(old_words, new_words)
        self.assertEqual(result, DiffResult(backspaces=4, new_text=""))  # 'test' only

    def test_middle_modification(self):
        """Test modifying a word in the middle."""
        old_words = [
            DictationWord(id=1, text="hello "),
            DictationWord(id=2, text="beautiful "),
            DictationWord(id=3, text="world")
        ]
        new_words = [
            DictationWord(id=1, text="hello "),
            DictationWord(id=4, text="wonderful "),
            DictationWord(id=3, text="world")
        ]
        result = self.engine.compare(old_words, new_words)
        self.assertEqual(result, DiffResult(backspaces=15, new_text="wonderful world"))  # 'beautiful world'

    def test_middle_insertion(self):
        """Test inserting a word in the middle."""
        old_words = [
            DictationWord(id=1, text="hello "),
            DictationWord(id=2, text="world")
        ]
        new_words = [
            DictationWord(id=1, text="hello "),
            DictationWord(id=3, text="beautiful "),
            DictationWord(id=2, text="world")
        ]
        result = self.engine.compare(old_words, new_words)
        self.assertEqual(result, DiffResult(backspaces=5, new_text="beautiful world"))  # 'world'

    def test_middle_deletion(self):
        """Test deleting a word from the middle."""
        old_words = [
            DictationWord(id=1, text="hello "),
            DictationWord(id=2, text="beautiful "),
            DictationWord(id=3, text="world")
        ]
        new_words = [
            DictationWord(id=1, text="hello "),
            DictationWord(id=3, text="world")
        ]
        result = self.engine.compare(old_words, new_words)
        self.assertEqual(result, DiffResult(backspaces=15, new_text="world"))  # 'beautiful world'

    def test_complex_changes(self):
        """Test multiple simultaneous changes."""
        old_words = [
            DictationWord(id=1, text="hello "),
            DictationWord(id=2, text="beautiful "),
            DictationWord(id=3, text="world "),
            DictationWord(id=4, text="today")
        ]
        new_words = [
            DictationWord(id=1, text="hello "),
            DictationWord(id=5, text="wonderful "),
            DictationWord(id=6, text="new "),
            DictationWord(id=7, text="universe")
        ]
        result = self.engine.compare(old_words, new_words)
        self.assertEqual(result, DiffResult(backspaces=21, new_text="wonderful new universe"))  # 'beautiful world today'

    def test_empty_old_list(self):
        """Test with empty old list."""
        new_words = [
            DictationWord(id=1, text="hello "),
            DictationWord(id=2, text="world")
        ]
        result = self.engine.compare([], new_words)
        self.assertEqual(result, DiffResult(backspaces=0, new_text="hello world"))

    def test_empty_new_list(self):
        """Test with empty new list."""
        old_words = [
            DictationWord(id=1, text="hello "),
            DictationWord(id=2, text="world")
        ]
        result = self.engine.compare(old_words, [])
        self.assertEqual(result, DiffResult(backspaces=11, new_text=""))


    def test_consecutive_words_from_xml(self):
        """Test that words extracted from consecutive XML tags are properly spaced."""
        # Model controls spacing - each word should include its trailing space if needed
        old_words = []
        new_words = [
            DictationWord(id=10, text="This "),
            DictationWord(id=20, text="is "),
            DictationWord(id=30, text="test")
        ]
        result = self.engine.compare(old_words, new_words)
        self.assertEqual(result, DiffResult(backspaces=0, new_text="This is test"))


if __name__ == '__main__':
    unittest.main()