"""Test suite for XML Stream Processor using pytest."""

import sys
import os
import pytest

# Add parent directory to path for imports
parent_dir = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, parent_dir)

from xml_stream_processor import XMLStreamProcessor
from keyboard_injector import MockKeyboardInjector


class TestXMLStreamProcessor:
    """Test cases for XMLStreamProcessor functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.keyboard = MockKeyboardInjector()
        self.processor = XMLStreamProcessor(self.keyboard)
    
    def test_basic_word_replacement(self):
        """Test basic word replacement with backspace calculation."""
        initial_words = {10: "The ", 20: "quick ", 30: "brown "}
        self.processor.reset(initial_words)
        
        self.processor.process_chunk("<20>fast </20>")
        self.processor.end_stream()
        
        # Should backspace to position after "The " then emit "fast brown "
        expected_operations = [
            ('bksp', 12),  # len("The quick brown ") - len("The ")
            ('emit', "fast "),
            ('emit', "brown ")  # Gap fill from end_stream
        ]
        assert self.keyboard.operations == expected_operations
        assert self.keyboard.output == "fast brown "
    
    def test_xml_fragmentation(self):
        """Test XML tags split across multiple chunks."""
        initial_words = {10: "Hi "}
        self.processor.reset(initial_words)
        
        # Fragment the XML tag across chunks
        self.processor.process_chunk("<1")
        self.processor.process_chunk("0>By")
        self.processor.process_chunk("e </1")
        self.processor.process_chunk("0>")
        
        expected_operations = [
            ('bksp', 3),  # len("Hi ") - len("")
            ('emit', "Bye ")
        ]
        assert self.keyboard.operations == expected_operations
        assert self.keyboard.output == "Bye "
    
    def test_gap_filling(self):
        """Test gap filling between non-consecutive updates."""
        initial_words = {10: "The ", 20: "quick ", 30: "brown ", 40: "fox "}
        self.processor.reset(initial_words)
        
        self.processor.process_chunk("<20>fast </20>")
        self.processor.process_chunk("<40>dog </40>")
        self.processor.end_stream()
        
        expected_operations = [
            ('bksp', 16),  # len("The quick brown fox ") - len("The ")
            ('emit', "fast "),
            ('emit', "brown "),  # Gap fill word 30
            ('emit', "dog ")
        ]
        assert self.keyboard.operations == expected_operations
        assert self.keyboard.output == "fast brown dog "
    
    def test_empty_word_deletion(self):
        """Test empty word updates delete from state."""
        initial_words = {10: "The ", 20: "quick ", 30: "brown "}
        self.processor.reset(initial_words)
        
        self.processor.process_chunk("<20></20>")
        self.processor.end_stream()
        
        expected_operations = [
            ('bksp', 12),  # len("The quick brown ") - len("The ")
            ('emit', ''),  # Emit empty string for deleted word 20
            ('emit', "brown ")  # End stream emits remaining word 30
        ]
        assert self.keyboard.operations == expected_operations
        assert self.keyboard.output == "brown "
        
        # Verify word was set to empty string (not removed from dict)
        assert self.processor.current_words[20] == ''
    
    def test_multiple_tags_single_chunk(self):
        """Test multiple complete and partial tags in one chunk."""
        initial_words = {10: "The ", 20: "quick ", 30: "brown "}
        self.processor.reset(initial_words)
        
        # Multiple complete tags plus partial
        self.processor.process_chunk("<10>A </10><20>fast </20><30>red")
        self.processor.end_stream()
        
        expected_operations = [
            ('bksp', 16),  # len("The quick brown ") - len("")
            ('emit', "A "),
            ('emit', "fast "),
            ('emit', "brown ")  # Word 30 unchanged, partial tag ignored
        ]
        assert self.keyboard.operations == expected_operations
        assert self.keyboard.output == "A fast brown "
    
    def test_no_updates_stream(self):
        """Test end_stream with no updates processed."""
        initial_words = {10: "Hello ", 20: "world "}
        self.processor.reset(initial_words)
        
        # No updates, just end stream
        self.processor.end_stream()
        
        # Should not emit anything since no backspace was performed
        assert self.keyboard.operations == []
        assert self.keyboard.output == ""
    
    def test_insertion_of_new_sequences(self):
        """Test sequences not in initial state."""
        initial_words = {10: "The ", 30: "brown "}
        self.processor.reset(initial_words)
        
        self.processor.process_chunk("<10>A </10>")
        self.processor.process_chunk("<20>fast </20>")
        self.processor.process_chunk("<30>red </30>")
        self.processor.end_stream()
        
        expected_operations = [
            ('bksp', 10),  # len("The brown ") - len("")
            ('emit', "A "),
            ('emit', "fast "),  # New sequence 20
            ('emit', "red ")
        ]
        assert self.keyboard.operations == expected_operations
        assert self.keyboard.output == "A fast red "
    
    def test_extreme_fragmentation(self):
        """Test XML split into individual characters."""
        initial_words = {10: "Hi "}
        self.processor.reset(initial_words)
        
        chunks = ["<", "1", "0", ">", "B", "y", "e", " ", "<", "/", "1", "0", ">"]
        for chunk in chunks:
            self.processor.process_chunk(chunk)
        
        expected_operations = [
            ('bksp', 3),
            ('emit', "Bye ")
        ]
        assert self.keyboard.operations == expected_operations
        assert self.keyboard.output == "Bye "
    
    def test_buffer_state_after_end_stream(self):
        """Test xml_buffer is cleared after end_stream."""
        initial_words = {10: "Hi "}
        self.processor.reset(initial_words)
        
        # Leave partial tag in buffer
        self.processor.process_chunk("<10>Hey </10><20>partial")
        assert self.processor.xml_buffer == "<20>partial"
        
        self.processor.end_stream()
        assert self.processor.xml_buffer == ""
    
    def test_complex_multiupdate_stream(self):
        """Test complex scenario with multiple updates and gaps."""
        initial_words = {10: "I ", 20: "will ", 30: "go ", 40: "to ", 50: "the ", 60: "store "}
        self.processor.reset(initial_words)
        
        self.processor.process_chunk("<20>might </20>")
        self.processor.process_chunk("<60>market </60>")
        self.processor.end_stream()
        
        expected_operations = [
            ('bksp', 21),  # len("I will go to the store ") - len("I ")
            ('emit', "might "),
            ('emit', "go "),     # Gap fill
            ('emit', "to "),     # Gap fill  
            ('emit', "the "),    # Gap fill
            ('emit', "market ")
        ]
        assert self.keyboard.operations == expected_operations
        assert self.keyboard.output == "might go to the market "
    
    def test_deletion_creates_permanent_gap(self):
        """Test deleted words create gaps in future emissions."""
        initial_words = {10: "The ", 20: "quick ", 30: "brown ", 40: "fox "}
        self.processor.reset(initial_words)
        
        # Delete word 20
        self.processor.process_chunk("<20></20>")
        # Update word 40, should skip deleted 20 in gap fill
        self.processor.process_chunk("<40>dog </40>")
        self.processor.end_stream()
        
        expected_operations = [
            ('bksp', 16),  # Initial backspace
            ('emit', ''),   # Emit empty string for deleted word 20
            ('emit', "brown "),  # Gap fill word 30 (20 deleted)
            ('emit', "dog ")
        ]
        assert self.keyboard.operations == expected_operations
        assert self.keyboard.output == "brown dog "
    
    def test_empty_initial_state(self):
        """Test processor with empty initial word mapping."""
        self.processor.reset({})
        
        self.processor.process_chunk("<10>Hello </10>")
        self.processor.end_stream()
        
        # No backspace needed with empty initial state
        expected_operations = [
            ('emit', "Hello ")
        ]
        assert self.keyboard.operations == expected_operations
        assert self.keyboard.output == "Hello "
    
    def test_consecutive_deletions(self):
        """Test multiple consecutive word deletions."""
        initial_words = {10: "The ", 20: "quick ", 30: "brown ", 40: "fox "}
        self.processor.reset(initial_words)
        
        self.processor.process_chunk("<20></20>")
        self.processor.process_chunk("<30></30>")
        self.processor.end_stream()
        
        expected_operations = [
            ('bksp', 16),  # Initial backspace for deletion of word 20
            ('emit', ''),   # Emit empty string for deleted word 20
            ('emit', ''),   # Emit empty string for deleted word 30
            ('emit', "fox ")  # End stream emits remaining word 40
        ]
        assert self.keyboard.operations == expected_operations
        assert self.keyboard.output == "fox "
        
        # Verify both words were set to empty strings
        assert self.processor.current_words[20] == ''
        assert self.processor.current_words[30] == ''
    
    def test_replacement_then_deletion(self):
        """Test word replacement followed by deletion of same word."""
        initial_words = {10: "The ", 20: "quick "}
        self.processor.reset(initial_words)
        
        self.processor.process_chunk("<20>fast </20>")
        self.processor.process_chunk("<20></20>")
        
        expected_operations = [
            ('bksp', 6),   # len("The quick ") - len("The ")
            ('emit', "fast "),
            ('bksp', 5),   # Backspace "fast " to reposition for deletion
            ('emit', ''),  # Emit empty string for deleted word 20
        ]
        assert self.keyboard.operations == expected_operations
        assert self.keyboard.output == ""
        
        # Word should be set to empty string
        assert self.processor.current_words[20] == ''
    
    def test_large_sequence_numbers(self):
        """Test with large sequence numbers."""
        initial_words = {1000: "First ", 2000: "Second "}
        self.processor.reset(initial_words)
        
        self.processor.process_chunk("<2000>Last </2000>")
        self.processor.end_stream()
        
        expected_operations = [
            ('bksp', 7),  # len("First Second ") - len("First ")
            ('emit', "Last ")
        ]
        assert self.keyboard.operations == expected_operations
        assert self.keyboard.output == "Last "
    
    def test_mixed_operations_single_chunk(self):
        """Test replacement and deletion in same chunk."""
        initial_words = {10: "The ", 20: "quick ", 30: "brown ", 40: "fox "}
        self.processor.reset(initial_words)
        
        # Replace word 10, delete word 20, replace word 30
        self.processor.process_chunk("<10>A </10><20></20><30>red </30>")
        self.processor.end_stream()
        
        expected_operations = [
            ('bksp', 20),  # Full backspace from beginning
            ('emit', "A "),
            ('emit', ''),   # Emit empty string for deleted word 20
            ('emit', "red "),
            ('emit', "fox ")  # End stream emission
        ]
        assert self.keyboard.operations == expected_operations
        assert self.keyboard.output == "A red fox "
        assert self.processor.current_words[20] == ''
    
    def test_reset_clears_state(self):
        """Test reset properly clears processor state."""
        initial_words = {10: "Hello ", 20: "world "}
        self.processor.reset(initial_words)
        
        self.processor.process_chunk("<10>Hi </10>")
        assert self.processor.backspace_performed is True
        assert self.processor.last_emitted_seq == 10
        
        # Reset with new words
        new_words = {100: "Good ", 200: "morning "}
        self.processor.reset(new_words)
        
        assert self.processor.current_words == new_words
        assert self.processor.xml_buffer == ""
        assert self.processor.backspace_performed is False
        assert self.processor.last_emitted_seq == 0
    
    def test_unicode_content(self):
        """Test processor handles Unicode content correctly."""
        initial_words = {10: "Hello ", 20: "世界 "}
        self.processor.reset(initial_words)
        
        self.processor.process_chunk("<20>🌍 </20>")
        self.processor.end_stream()
        
        expected_operations = [
            ('bksp', 3),  # len("Hello 世界 ") - len("Hello ")
            ('emit', "🌍 ")
        ]
        assert self.keyboard.operations == expected_operations
        assert self.keyboard.output == "🌍 "
    
    def test_whitespace_preservation(self):
        """Test various whitespace characters are preserved."""
        initial_words = {10: "Tab\t", 20: "newline\n", 30: "space "}
        self.processor.reset(initial_words)
        
        self.processor.process_chunk("<20>return\r</20>")
        self.processor.end_stream()
        
        expected_operations = [
            ('bksp', 14),  # Backspace after "Tab\t"
            ('emit', "return\r"),
            ('emit', "space ")  # End stream
        ]
        assert self.keyboard.operations == expected_operations
        assert self.keyboard.output == "return\rspace "
    
    def test_malformed_xml_ignored(self):
        """Test malformed XML tags are ignored."""
        initial_words = {10: "Hello "}
        self.processor.reset(initial_words)
        
        # Send malformed XML that can't be parsed
        self.processor.process_chunk("<invalid>text</invalid>")
        self.processor.process_chunk("<10>Hi </10>")
        self.processor.end_stream()
        
        # Should only process the valid tag
        expected_operations = [
            ('bksp', 6),  # len("Hello ") - len("")
            ('emit', "Hi ")
        ]
        assert self.keyboard.operations == expected_operations
        assert self.keyboard.output == "Hi "
