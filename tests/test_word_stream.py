"""
Tests for the word_stream module.

This module contains tests for the WordStreamParser class, focusing on its
ability to handle various forms of input, including complete tags, partial
tags, invalid tags, and empty/noisy chunks.
"""

import unittest
from lib.word_stream import WordStreamParser, DictationWord


class TestWordStreamParser(unittest.TestCase):
    """Test cases for the WordStreamParser class."""

    def setUp(self):
        """Set up a fresh parser for each test."""
        self.parser = WordStreamParser()

    def test_complete_tags_single_chunk(self):
        """Test parsing complete tags in a single chunk."""
        # Single complete tag
        words = self.parser.parse("<10>hello</10>")
        self.assertEqual(len(words), 1)
        self.assertEqual(words[0].id, 10)
        self.assertEqual(words[0].text, "hello")
        self.assertEqual(self.parser.get_buffer(), "")

        # Multiple complete tags
        self.parser.clear_buffer()
        words = self.parser.parse("<20>world</20><30>test</30>")
        self.assertEqual(len(words), 2)
        self.assertEqual(words[0].id, 20)
        self.assertEqual(words[0].text, "world")
        self.assertEqual(words[1].id, 30)
        self.assertEqual(words[1].text, "test")
        self.assertEqual(self.parser.get_buffer(), "")

    def test_partial_tags_start(self):
        """Test parsing partial tags where the start is incomplete."""
        # First chunk has incomplete opening tag
        words = self.parser.parse("<1")
        self.assertEqual(len(words), 0)
        self.assertEqual(self.parser.get_buffer(), "<1")

        # Second chunk completes the tag
        words = self.parser.parse("0>hello</10>")
        self.assertEqual(len(words), 1)
        self.assertEqual(words[0].id, 10)
        self.assertEqual(words[0].text, "hello")
        self.assertEqual(self.parser.get_buffer(), "")

    def test_partial_tags_middle(self):
        """Test parsing partial tags where the middle is split."""
        # First chunk has incomplete content
        words = self.parser.parse("<20>wo")
        self.assertEqual(len(words), 0)
        self.assertEqual(self.parser.get_buffer(), "<20>wo")

        # Second chunk completes the tag
        words = self.parser.parse("rld</20>")
        self.assertEqual(len(words), 1)
        self.assertEqual(words[0].id, 20)
        self.assertEqual(words[0].text, "world")
        self.assertEqual(self.parser.get_buffer(), "")

    def test_partial_tags_end(self):
        """Test parsing partial tags where the end is incomplete."""
        # First chunk has incomplete closing tag
        words = self.parser.parse("<30>word</3")
        self.assertEqual(len(words), 0)
        self.assertEqual(self.parser.get_buffer(), "<30>word</3")

        # Second chunk completes the tag
        words = self.parser.parse("0>")
        self.assertEqual(len(words), 1)
        self.assertEqual(words[0].id, 30)
        self.assertEqual(words[0].text, "word")
        self.assertEqual(self.parser.get_buffer(), "")

    def test_multiple_partial_tags(self):
        """Test parsing multiple partial tags across chunks."""
        # First chunk has one complete tag and one incomplete tag
        words = self.parser.parse("<40>word</40><5")
        self.assertEqual(len(words), 1)
        self.assertEqual(words[0].id, 40)
        self.assertEqual(words[0].text, "word")
        self.assertEqual(self.parser.get_buffer(), "<5")

        # Second chunk completes the second tag
        words = self.parser.parse("0>another</50>")
        self.assertEqual(len(words), 1)
        self.assertEqual(words[0].id, 50)
        self.assertEqual(words[0].text, "another")
        self.assertEqual(self.parser.get_buffer(), "")

    def test_invalid_tags(self):
        """Test parsing invalid or malformed tags."""
        # Tag with no ID
        words = self.parser.parse("<>word</>")
        self.assertEqual(len(words), 0)
        self.assertEqual(self.parser.get_buffer(), "<>word</>")

        # Tag with non-matching IDs
        self.parser.clear_buffer()
        words = self.parser.parse("<10>word</20>")
        self.assertEqual(len(words), 0)
        self.assertEqual(self.parser.get_buffer(), "<10>word</20>")

        # Tag with no closing tag (remains in buffer)
        self.parser.clear_buffer()
        words = self.parser.parse("<10>word")
        self.assertEqual(len(words), 0)
        self.assertEqual(self.parser.get_buffer(), "<10>word")

    def test_empty_noisy_chunks(self):
        """Test parsing empty strings and non-XML text between valid tags."""
        # Empty string
        words = self.parser.parse("")
        self.assertEqual(len(words), 0)
        self.assertEqual(self.parser.get_buffer(), "")

        # Whitespace
        words = self.parser.parse("   \n\t   ")
        self.assertEqual(len(words), 0)
        self.assertEqual(self.parser.get_buffer(), "   \n\t   ")

        # Non-XML text
        self.parser.clear_buffer()
        words = self.parser.parse("This is not XML")
        self.assertEqual(len(words), 0)
        self.assertEqual(self.parser.get_buffer(), "This is not XML")

        # Non-XML text with valid tag
        self.parser.clear_buffer()
        words = self.parser.parse("Before <60>valid</60> After")
        self.assertEqual(len(words), 1)
        self.assertEqual(words[0].id, 60)
        self.assertEqual(words[0].text, "valid")
        self.assertEqual(self.parser.get_buffer(), "Before After")

    def test_complex_mixed_scenario(self):
        """Test a complex scenario with mixed complete and partial tags."""
        # First chunk: one complete tag, one partial at start
        words = self.parser.parse("<70>complete</70><8")
        self.assertEqual(len(words), 1)
        self.assertEqual(words[0].id, 70)
        self.assertEqual(words[0].text, "complete")
        self.assertEqual(self.parser.get_buffer(), "<8")

        # Second chunk: completes previous tag, adds one complete, starts another
        words = self.parser.parse("0>partial1</80><90>complete2</90><1")
        self.assertEqual(len(words), 2)
        self.assertEqual(words[0].id, 80)
        self.assertEqual(words[0].text, "partial1")
        self.assertEqual(words[1].id, 90)
        self.assertEqual(words[1].text, "complete2")
        self.assertEqual(self.parser.get_buffer(), "<1")

        # Third chunk: completes previous tag, adds noise
        words = self.parser.parse("00>partial2</100> some noise")
        self.assertEqual(len(words), 1)
        self.assertEqual(words[0].id, 100)
        self.assertEqual(words[0].text, "partial2")
        self.assertEqual(self.parser.get_buffer(), " some noise")

    def test_tags_with_special_characters(self):
        """Test parsing tags with special characters in the content."""
        # Tag with special characters
        words = self.parser.parse("<110>special < > & chars</110>")
        self.assertEqual(len(words), 1)
        self.assertEqual(words[0].id, 110)
        self.assertEqual(words[0].text, "special < > & chars")
        self.assertEqual(self.parser.get_buffer(), "")

        # Tag with newlines and tabs
        self.parser.clear_buffer()
        words = self.parser.parse("<120>multi\nline\ttext</120>")
        self.assertEqual(len(words), 1)
        self.assertEqual(words[0].id, 120)
        self.assertEqual(words[0].text, "multi\nline\ttext")
        self.assertEqual(self.parser.get_buffer(), "")

    def test_empty_content(self):
        """Test parsing tags with empty content."""
        words = self.parser.parse("<130></130>")
        self.assertEqual(len(words), 1)
        self.assertEqual(words[0].id, 130)
        self.assertEqual(words[0].text, "")
        self.assertEqual(self.parser.get_buffer(), "")

    def test_consecutive_xml_tags(self):
        """Test parsing consecutive XML tags without spaces."""
        words = self.parser.parse("<10>This</10><20>is</20><30>a</30><40>dictation</40><50>test</50>")
        self.assertEqual(len(words), 5)
        self.assertEqual(words[0].text, "This")
        self.assertEqual(words[1].text, "is")
        self.assertEqual(words[2].text, "a")
        self.assertEqual(words[3].text, "dictation")
        self.assertEqual(words[4].text, "test")
        self.assertEqual(self.parser.get_buffer(), "")

    def test_mixed_xml_and_text(self):
        """Test parsing XML tags mixed with regular text."""
        # This simulates what might happen if there's text before/after XML
        words = self.parser.parse("Start <10>This</10><20>is</20><30>test</30> End")
        self.assertEqual(len(words), 3)
        self.assertEqual(words[0].text, "This")
        self.assertEqual(words[1].text, "is")
        self.assertEqual(words[2].text, "test")
        # Buffer should contain the non-XML text with normalized spacing
        self.assertEqual(self.parser.get_buffer(), "Start End")


if __name__ == "__main__":
    unittest.main()