"""
Test XML entity unescaping in XMLStreamProcessor.
"""
import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib', 'xml-stream'))

from xml_stream_processor import XMLStreamProcessor
from keyboard_injector import MockKeyboardInjector


class TestXMLEntityUnescaping(unittest.TestCase):
    """Test that XML entities are properly unescaped."""

    def setUp(self):
        self.keyboard = MockKeyboardInjector()
        self.processor = XMLStreamProcessor(self.keyboard)

    def test_ampersand_unescaping(self):
        """Test that &amp; is unescaped to &."""
        self.processor.reset({})
        self.processor.process_chunk('<10>AT&amp;T Corporation </10>')
        self.processor.end_stream()

        output = self.keyboard.output
        self.assertEqual(output, "AT&T Corporation ", f"Expected 'AT&T Corporation ' but got '{output}'")

    def test_less_than_unescaping(self):
        """Test that &lt; is unescaped to <."""
        self.processor.reset({})
        self.processor.process_chunk('<10>Value &lt; 10 </10>')
        self.processor.end_stream()

        output = self.keyboard.output
        self.assertEqual(output, "Value < 10 ", f"Expected 'Value < 10 ' but got '{output}'")

    def test_greater_than_unescaping(self):
        """Test that &gt; is unescaped to >."""
        self.processor.reset({})
        self.processor.process_chunk('<10>Value &gt; 5 </10>')
        self.processor.end_stream()

        output = self.keyboard.output
        self.assertEqual(output, "Value > 5 ", f"Expected 'Value > 5 ' but got '{output}'")

    def test_multiple_entities_in_one_tag(self):
        """Test multiple entities in a single tag."""
        self.processor.reset({})
        self.processor.process_chunk('<10>Company &amp; Sons &lt; &gt; </10>')
        self.processor.end_stream()

        output = self.keyboard.output
        self.assertEqual(output, "Company & Sons < > ", f"Expected 'Company & Sons < > ' but got '{output}'")

    def test_entities_across_multiple_tags(self):
        """Test entities across multiple tags."""
        self.processor.reset({})
        self.processor.process_chunk('<10>AT&amp;T </10><20>&lt;test&gt; </20><30>done</30>')
        self.processor.end_stream()

        output = self.keyboard.output
        self.assertEqual(output, "AT&T <test> done ", f"Expected 'AT&T <test> done ' but got '{output}'")

    def test_no_entities_unchanged(self):
        """Test that content without entities is unchanged."""
        self.processor.reset({})
        self.processor.process_chunk('<10>Normal text </10>')
        self.processor.end_stream()

        output = self.keyboard.output
        self.assertEqual(output, "Normal text ", f"Expected 'Normal text ' but got '{output}'")


if __name__ == '__main__':
    unittest.main(verbosity=2)