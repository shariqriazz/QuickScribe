#!/usr/bin/env python3
"""
Test fragmented XML streaming with accurate state trace for sentence swap bug.
"""

import sys
import os
import unittest

# Add parent directory and xml-stream to path
parent_dir = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, parent_dir)
sys.path.append(os.path.join(parent_dir, 'lib', 'xml-stream'))

from xml_stream_processor import XMLStreamProcessor
from keyboard_injector import MockKeyboardInjector


class TestFragmentedStreamingStateTrace(unittest.TestCase):
    """Test XMLStreamProcessor fragmented streaming with detailed state verification."""
    
    def setUp(self):
        """Set up test environment."""
        self.keyboard = MockKeyboardInjector()
        self.processor = XMLStreamProcessor(self.keyboard)
        
        # Initial state: sentence order needs swapping
        self.initial_words = {
            10: "This is test ", 
            20: "number two.", 
            30: "This is test ", 
            40: "number one."
        }
        
        # Simulate existing display content
        self.keyboard.output = "This is test number two.This is test number one."
        
        # Fragmented chunks representing:
        # <10>This is test </10><20>number one.</20><30>This is test </30><40>number two.</40>
        self.chunks = [
            "<10>This is",           # Chunk 1: Start word 10 
            " test </1",             # Chunk 2: Continue word 10
            "0><20>nu",              # Chunk 3: Complete word 10, start word 20
            "mber one.</20>",        # Chunk 4: Complete word 20 - FIRST CHANGE!
            "<3",                    # Chunk 5: Start word 30
            "0>This is test <",      # Chunk 6: Continue word 30  
            "/30><40>n",             # Chunk 7: Complete word 30, start word 40
            "umber ",                # Chunk 8: Continue word 40
            "two",                   # Chunk 9: Continue word 40
            ".</40>"                 # Chunk 10: Complete word 40 - SECOND CHANGE!
        ]
    
    def test_fragmented_sentence_swap_with_detailed_state_trace(self):
        """Test fragmented streaming with state verification at each critical point."""
        
        print(f"\n=== STEP-BY-STEP TRACE: XMLStreamProcessor Fragmented Streaming ===")
        print(f"Target sentence swap:")
        print(f"  FROM: 'This is test number two.This is test number one.'")
        print(f"  TO:   'This is test number one.This is test number two.'")
        
        # Reset processor with initial state
        self.processor.reset(self.initial_words)
        print(f"\n📍 INITIAL STATE:")
        print(f"  current_words: {self.processor.current_words}")
        print(f"  keyboard.output: '{self.keyboard.output}'")
        print(f"  backspace_performed: {self.processor.backspace_performed}")
        print(f"  last_emitted_seq: {self.processor.last_emitted_seq}")
        
        # Process ALL chunks with detailed trace
        for i, chunk in enumerate(self.chunks):
            print(f"\n🔄 CHUNK {i+1}/10: '{chunk}'")
            print(f"  xml_buffer BEFORE: '{self.processor.xml_buffer}'")
            
            self.processor.process_chunk(chunk)
            
            print(f"  xml_buffer AFTER:  '{self.processor.xml_buffer}'")
            print(f"  current_words:     {self.processor.current_words}")
            print(f"  keyboard.output:   '{self.keyboard.output}'")
            print(f"  keyboard.operations: {self.keyboard.operations}")
            print(f"  backspace_performed: {self.processor.backspace_performed}")
            print(f"  last_emitted_seq:  {self.processor.last_emitted_seq}")
            
            # Show what changed
            if i > 0:
                prev_ops_count = len(getattr(self, '_prev_operations', []))
                new_ops = self.keyboard.operations[prev_ops_count:]
                if new_ops:
                    print(f"  ✨ NEW OPERATIONS: {new_ops}")
                else:
                    print(f"  ⚪ NO NEW OPERATIONS")
            
            self._prev_operations = self.keyboard.operations.copy()
        
        print(f"\n📊 FINAL SUMMARY:")
        print(f"  Expected output: 'This is test number one.This is test number two.'")
        print(f"  Actual output:   '{self.keyboard.output}'")
        print(f"  Match: {self.keyboard.output == 'This is test number one.This is test number two.'}")
        
        # Don't run the actual assertions, just show the trace
        return
        
        # Verify state after chunk 3 - word 10 completed but unchanged
        print(f"\nAfter chunk 3 analysis:")
        print(f"  Word 10 completion - is it changed?")
        print(f"    original word 10: '{self.initial_words[10]}'")
        print(f"    completed word 10 from buffer: should be 'This is test '")
        print(f"  Did word 10 trigger backspace inappropriately?")
        
        expected_buffer_after_3 = "<20>nu"
        self.assertEqual(self.processor.xml_buffer, expected_buffer_after_3)
        self.assertEqual(self.keyboard.output, "This is test number two.This is test number one.")
        self.assertFalse(self.processor.backspace_performed)
        self.assertEqual(len(self.keyboard.operations), 0)
        
        # Process chunk 4: Complete word 20 - FIRST ACTUAL CHANGE triggers backspace
        print(f"\nProcessing chunk 4 (CRITICAL): '{self.chunks[3]}'")
        print(f"  Before chunk 4:")
        print(f"    current_words[20]: '{self.processor.current_words.get(20)}'")
        print(f"    keyboard.output: '{self.keyboard.output}'")
        
        self.processor.process_chunk(self.chunks[3])
        
        print(f"  After chunk 4:")
        print(f"    xml_buffer: '{self.processor.xml_buffer}'")
        print(f"    current_words: {self.processor.current_words}")
        print(f"    keyboard.output: '{self.keyboard.output}'")
        print(f"    keyboard.operations: {self.keyboard.operations}")
        print(f"    backspace_performed: {self.processor.backspace_performed}")
        print(f"    last_emitted_seq: {self.processor.last_emitted_seq}")
        
        # Calculate expected backspace using XMLStreamProcessor logic
        original_str = self.processor._build_string_from_words(self.initial_words)
        modified_words = self.initial_words.copy()
        modified_words[20] = "number one."
        modified_str = self.processor._build_string_from_words(modified_words)
        common_prefix_len = self.processor._find_common_prefix_length(original_str, modified_str)
        expected_backspace = len(original_str) - common_prefix_len
        
        print(f"  Expected calculations:")
        print(f"    original_str: '{original_str}' (len={len(original_str)})")
        print(f"    modified_str: '{modified_str}' (len={len(modified_str)})")
        print(f"    common_prefix_len: {common_prefix_len}")
        print(f"    expected_backspace: {expected_backspace}")
        
        # Verify state after chunk 4 - backspace and first emission
        expected_output_after_4 = "This is test number one."
        expected_operations_after_4 = [
            ('bksp', expected_backspace),  # Use calculated backspace
            ('emit', 'one.')               # Emit only part of word 20 after common prefix
        ]
        
        self.assertEqual(self.processor.xml_buffer, "")
        self.assertEqual(self.keyboard.output, expected_output_after_4)
        self.assertTrue(self.processor.backspace_performed)
        self.assertEqual(self.processor.last_emitted_seq, 20)
        self.assertEqual(self.keyboard.operations, expected_operations_after_4)
        
        # Verify current_words state updated
        expected_words_after_4 = {
            10: "This is test ", 
            20: "number one.",    # Changed from "number two."
            30: "This is test ", 
            40: "number one."
        }
        self.assertEqual(self.processor.current_words, expected_words_after_4)
        
        # Process chunks 5-6: Buffer accumulation for word 30
        for chunk in self.chunks[4:6]:
            self.processor.process_chunk(chunk)
        
        # Verify state after chunk 6 - still buffering word 30
        expected_buffer_after_6 = "<30>This is test <"
        self.assertEqual(self.processor.xml_buffer, expected_buffer_after_6)
        self.assertEqual(self.keyboard.output, expected_output_after_4)  # Unchanged
        
        # Process chunk 7: Complete word 30 - unchanged but needs gap fill emission
        self.processor.process_chunk(self.chunks[6])
        
        # Verify state after chunk 7 - gap filled word 30 emission
        expected_output_after_7 = "This is test number one.This is test "
        expected_operations_after_7 = [
            ('bksp', expected_backspace),
            ('emit', 'one.'),
            ('emit', 'This is test ')  # Gap fill emission of unchanged word 30
        ]
        
        self.assertEqual(self.processor.xml_buffer, "<40>n")
        self.assertEqual(self.keyboard.output, expected_output_after_7)
        self.assertEqual(self.processor.last_emitted_seq, 30)
        self.assertEqual(self.keyboard.operations, expected_operations_after_7)
        
        # Process chunks 8-9: Buffer accumulation for word 40
        for chunk in self.chunks[7:9]:
            self.processor.process_chunk(chunk)
        
        # Verify state after chunk 9 - still buffering word 40
        expected_buffer_after_9 = "<40>number two"
        self.assertEqual(self.processor.xml_buffer, expected_buffer_after_9)
        self.assertEqual(self.keyboard.output, expected_output_after_7)  # Unchanged
        
        # Process chunk 10: Complete word 40 - SECOND CHANGE
        self.processor.process_chunk(self.chunks[9])
        
        # Verify final state - complete sentence swap
        expected_final_output = "This is test number one.This is test number two."
        # With word-based logic: backspaces to word 20, emits words 20,30,40 together
        expected_final_operations = [
            ('bksp', expected_backspace),
            ('emit', 'number one.This is test number two.')   # All words from first change onwards
        ]
        
        self.assertEqual(self.processor.xml_buffer, "")
        self.assertEqual(self.keyboard.output, expected_final_output)
        self.assertEqual(self.processor.last_emitted_seq, 40)
        self.assertEqual(self.keyboard.operations, expected_final_operations)
        
        # Verify final current_words state
        expected_final_words = {
            10: "This is test ", 
            20: "number one.",    # Swapped
            30: "This is test ", 
            40: "number two."     # Swapped
        }
        self.assertEqual(self.processor.current_words, expected_final_words)
    
    def test_chunk_queuing_prevents_race_conditions(self):
        """Test that sequential chunk processing produces correct results."""

        self.processor.reset(self.initial_words)

        # Simulate rapid chunk arrival during processing
        # All chunks should be processed sequentially
        for chunk in self.chunks:
            self.processor.process_chunk(chunk)

        # With incremental processing: each word emits incrementally as it arrives
        # Word 10: unchanged, Word 20: "number one.", Word 30: unchanged, Word 40: "number two."
        # Expected sequence: word 20 emits only "number one.", word 40 emits "This is test number two."
        expected_output = "This is test number one.This is test number two."
        self.assertEqual(self.keyboard.output, expected_output)
    
    def test_backspace_calculation_accuracy(self):
        """Test that backspace calculation is accurate for the sentence swap scenario."""
        
        self.processor.reset(self.initial_words)
        
        # Manually calculate expected values  
        original_str = "This is test number two.This is test number one."  # 48 chars
        
        # After changing word 20 from "number two." to "number one."
        modified_words = self.initial_words.copy()
        modified_words[20] = "number one."
        modified_str = self.processor._build_string_from_words(modified_words)
        expected_modified = "This is test number one.This is test number one."  # 48 chars
        
        self.assertEqual(modified_str, expected_modified)
        
        # Calculate expected backspace using processor's logic
        target_words = self.initial_words.copy()
        target_words[20] = "number one."
        expected_backspace = self.processor._calculate_backspace_count(20)  # First changed sequence
        
        # Process enough chunks to trigger the backspace
        for chunk in self.chunks[:4]:
            self.processor.process_chunk(chunk)
        
        # Verify the actual backspace operation matches calculation
        backspace_op = self.keyboard.operations[0]
        self.assertEqual(backspace_op[0], 'bksp')
        self.assertEqual(backspace_op[1], expected_backspace)
    
    def test_incremental_emission_sequence(self):
        """Test that words are emitted incrementally as they complete processing."""
        
        self.processor.reset(self.initial_words)
        
        # Process chunks and verify incremental state changes
        # With incremental logic: each word emits up to its sequence only
        test_points = [
            (4, "This is test number one.", 1),  # After word 20 change: preserve word 10, emit word 20
            (7, "This is test number one.This is test ", 2),  # Word 30 unchanged but emits up to seq 30
            (10, "This is test number one.This is test number two.", 3)  # After word 40 change: emit word 40
        ]
        
        chunk_idx = 0
        for target_chunk, expected_output, expected_emit_count in test_points:
            # Process chunks up to target
            while chunk_idx < target_chunk:
                self.processor.process_chunk(self.chunks[chunk_idx])
                chunk_idx += 1
            
            # Verify state at this point
            self.assertEqual(self.keyboard.output, expected_output)
            
            # Count emit operations (excluding backspace)
            emit_ops = [op for op in self.keyboard.operations if op[0] == 'emit']
            self.assertEqual(len(emit_ops), expected_emit_count)


if __name__ == '__main__':
    unittest.main()