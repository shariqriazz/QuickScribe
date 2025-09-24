"""
Test streaming sequential word processing with gaps using MockOutputManager.
"""

import unittest
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.mock_output_manager import MockOutputManager
from lib.xdotool_queue import XdotoolQueue
from lib.sequential_processor_streaming import StreamingSequentialProcessor


class TestStreamingSequential(unittest.TestCase):
    """Test streaming sequential word processing with gaps."""
    
    def setUp(self):
        """Set up test environment."""
        self.mock_output_manager = MockOutputManager()
        self.xdotool_queue = XdotoolQueue(self.mock_output_manager)
        self.processor = StreamingSequentialProcessor()
        
    def test_exact_scenario_from_requirements(self):
        """
        Test the exact scenario from the requirements:
        Initial state: "The quick brown fox jumped over the stream"
        
        <20>fast</20> -> "The fast"
        <40>squirrel</40> -> "The fast brown squirrel"
        <60>across</60> -> "The fast brown squirrel jumped across"
        </update> -> "The fast brown squirrel jumped across the stream"
        """
        # Set original text
        original_text = "The quick brown fox jumped over the stream"
        self.processor.set_original_text(original_text)
        
        # Verify initial state
        self.assertEqual(self.processor.current_text, "")
        self.assertEqual(len(self.processor.original_words), 8)
        
        # Process <20>fast</20>
        # This should emit "The fast " (filling gap at word 10 with original)
        result = self.processor.process_word(20, "fast ")
        
        self.assertTrue(result.should_emit)
        self.assertEqual(result.text_to_type, "The fast ")
        self.assertEqual(result.backspace_count, 0)  # Nothing to backspace initially
        self.assertEqual(self.processor.get_current_text(), "The fast ")
        
        # Simulate xdotool operation
        self.xdotool_queue.queue_backspace_and_type(result.backspace_count, result.text_to_type)
        self.xdotool_queue.wait_for_completion()
        
        # Verify mock output manager state
        self.assertEqual(self.mock_output_manager.get_final_text(), "The fast ")
        
        # Process <40>squirrel</40>
        # This should backspace and emit "The fast brown squirrel " (filling gap at 30)
        result = self.processor.process_word(40, "squirrel ")
        
        self.assertTrue(result.should_emit)
        # Should only type "brown squirrel " since "The fast " is already there
        self.assertEqual(result.text_to_type, "brown squirrel ")
        self.assertEqual(result.backspace_count, 0)  # Common prefix is "The fast "
        self.assertEqual(self.processor.get_current_text(), "The fast brown squirrel ")
        
        # Simulate xdotool operation
        self.xdotool_queue.queue_backspace_and_type(result.backspace_count, result.text_to_type)
        self.xdotool_queue.wait_for_completion()
        
        # Process <60>across</60>
        # This should emit "The fast brown squirrel jumped across " (filling gap at 50)
        result = self.processor.process_word(60, "across ")
        
        self.assertTrue(result.should_emit)
        self.assertEqual(result.text_to_type, "jumped across ")
        self.assertEqual(result.backspace_count, 0)
        self.assertEqual(self.processor.get_current_text(), "The fast brown squirrel jumped across ")
        
        # Simulate xdotool operation
        self.xdotool_queue.queue_backspace_and_type(result.backspace_count, result.text_to_type)
        self.xdotool_queue.wait_for_completion()
        
        # Process remaining words (simulating </update>)
        # Process word 70 "the " (using original)
        result = self.processor.process_word(70, "the ")
        self.assertTrue(result.should_emit)
        self.assertEqual(result.text_to_type, "the ")
        
        # Process word 80 "stream" (using original)
        result = self.processor.process_word(80, "stream")
        self.assertTrue(result.should_emit)
        self.assertEqual(result.text_to_type, "stream")
        
        # Final text should match expected
        self.assertEqual(self.processor.get_current_text(), 
                        "The fast brown squirrel jumped across the stream")
    
    def test_backspace_on_correction(self):
        """Test that corrections properly backspace and retype."""
        original_text = "The quick brown fox"
        self.processor.set_original_text(original_text)
        
        # Process word 10 with original value
        result = self.processor.process_word(10, "The ")
        self.assertEqual(result.text_to_type, "The ")
        self.assertEqual(result.backspace_count, 0)
        
        # Process word 20 with change
        result = self.processor.process_word(20, "slow ")
        self.assertEqual(result.text_to_type, "slow ")
        self.assertEqual(result.backspace_count, 0)
        
        # Now go back and correct word 20 again
        self.processor = StreamingSequentialProcessor()
        self.processor.set_original_text(original_text)
        
        # Start over with different word 20
        result = self.processor.process_word(20, "fast ")
        self.assertEqual(result.text_to_type, "The fast ")
        self.assertEqual(self.processor.get_current_text(), "The fast ")
    
    def test_reject_out_of_order(self):
        """Test that out-of-order words are rejected."""
        original_text = "The quick brown fox"
        self.processor.set_original_text(original_text)
        
        # Process word 20 first
        result = self.processor.process_word(20, "quick ")
        self.assertTrue(result.should_emit)
        
        # Try to process word 10 (out of order)
        result = self.processor.process_word(10, "The ")
        self.assertFalse(result.should_emit)
        
        # Can still process word 30
        result = self.processor.process_word(30, "brown ")
        self.assertTrue(result.should_emit)
    
    def test_gap_filling(self):
        """Test that gaps are properly filled with original text."""
        original_text = "one two three four five"
        self.processor.set_original_text(original_text)
        
        # Skip word 10 and 20, process word 30
        result = self.processor.process_word(30, "THREE ")
        self.assertTrue(result.should_emit)
        # Should fill gaps with "one two " from original
        self.assertEqual(self.processor.get_current_text(), "one two THREE ")
        
        # Skip word 40, process word 50
        result = self.processor.process_word(50, "FIVE")
        self.assertTrue(result.should_emit)
        # Should fill gap with "four " from original
        self.assertEqual(self.processor.get_current_text(), "one two THREE four FIVE")


if __name__ == '__main__':
    unittest.main()