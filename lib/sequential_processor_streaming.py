"""
Sequential Word Processor for Streaming - Handles word updates with gap filling.
"""

from typing import Dict, List, Optional
from dataclasses import dataclass
from .word_stream import DictationWord


@dataclass
class ProcessingResult:
    """Result of sequential word processing."""
    backspace_count: int  # How many chars to backspace
    text_to_type: str     # What text to type
    should_emit: bool     # Whether to emit this update


class StreamingSequentialProcessor:
    """
    Processes streaming word updates with gap filling.
    
    Key behaviors:
    1. Words must arrive in sequential order (can skip IDs)
    2. When a word arrives, backspace to first change and emit all text forward
    3. Fill gaps with original text
    """
    
    def __init__(self, word_id_step: int = 10):
        """Initialize streaming sequential processor."""
        self.word_id_step = word_id_step
        self.original_words: Dict[int, str] = {}
        self.current_text = ""  # Track what's currently displayed
        self.processed_words: Dict[int, str] = {}  # Words we've processed
        self.last_processed_id = 0
        
    def set_original_text(self, text: str) -> None:
        """Set the original text for gap filling."""
        # Split text into words and assign sequential IDs
        words = text.split()
        self.original_words.clear()
        
        for i, word in enumerate(words):
            word_id = (i + 1) * self.word_id_step
            # Add space after each word except the last one
            word_text = word + (" " if i < len(words) - 1 else "")
            self.original_words[word_id] = word_text
        
        # Initialize current text to empty
        self.current_text = ""
        self.processed_words.clear()
        self.last_processed_id = 0
    
    def process_word(self, word_id: int, text: str) -> ProcessingResult:
        """
        Process a word update in streaming fashion.
        
        Args:
            word_id: The word ID (e.g., 10, 20, 40...)
            text: The word text with spacing (e.g., "fast ")
            
        Returns:
            ProcessingResult with backspace count and text to type
        """
        # Reject out-of-order words
        if word_id <= self.last_processed_id:
            return ProcessingResult(0, "", False)
        
        # Store this word
        self.processed_words[word_id] = text
        
        # Fill any gaps between last_processed_id and word_id
        gap_id = self.last_processed_id + self.word_id_step
        while gap_id < word_id:
            if gap_id in self.original_words and gap_id not in self.processed_words:
                # Fill gap with original text
                self.processed_words[gap_id] = self.original_words[gap_id]
            gap_id += self.word_id_step
        
        # Build the new complete text from all processed words
        new_text = self._build_text_from_processed()
        
        # Find common prefix between current and new text
        common_prefix_len = 0
        for i in range(min(len(self.current_text), len(new_text))):
            if self.current_text[i] == new_text[i]:
                common_prefix_len += 1
            else:
                break
        
        # Calculate backspace count and text to type
        backspace_count = len(self.current_text) - common_prefix_len
        text_to_type = new_text[common_prefix_len:]
        
        # Update state
        self.current_text = new_text
        self.last_processed_id = word_id
        
        return ProcessingResult(backspace_count, text_to_type, True)
    
    def _build_text_from_processed(self) -> str:
        """Build complete text from processed words."""
        result = ""
        
        # Get all word IDs we should include (processed + filled gaps)
        all_ids = sorted(self.processed_words.keys())
        
        for word_id in all_ids:
            result += self.processed_words[word_id]
        
        return result
    
    def get_current_text(self) -> str:
        """Get the current displayed text."""
        return self.current_text
    
    def reset(self) -> None:
        """Reset processor to initial state."""
        self.current_text = ""
        self.processed_words.clear()
        self.last_processed_id = 0