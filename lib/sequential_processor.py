"""
Sequential Word Processor - Handles word processing with gap filling and sequential ordering.
"""

from typing import Dict, List, Optional, Callable
from dataclasses import dataclass
from .word_stream import DictationWord


@dataclass
class ProcessingResult:
    """Result of sequential word processing."""
    words_to_emit: List[DictationWord]
    backspace_to_position: int
    should_emit: bool
    incremental_text: str = ""  # Text to emit for this specific update


class SequentialWordProcessor:
    """
    Processes words in sequential order with gap filling.
    
    Words must arrive in sequential ID order. When a word arrives:
    1. Process the word if it's the expected next ID
    2. Emit the word plus any consecutive words we can fill from original
    3. Update expected next ID to first unfillable gap
    """
    
    def __init__(self, word_id_step: int = 10):
        """Initialize sequential processor."""
        self.word_id_step = word_id_step
        self.expected_next_id = word_id_step
        self.original_words: Dict[int, str] = {}
        self.updated_words: Dict[int, str] = {}  # Words that have been changed
        self.emitted_words: Dict[int, str] = {}  # Words that have been emitted (reject further changes)
        self.first_change_id: Optional[int] = None
        self.last_emitted_position: int = 0  # Track last emitted character position
        
    def set_original_text(self, text: str, word_id_step: int = None) -> None:
        """Set the original text for gap filling."""
        if word_id_step is None:
            word_id_step = self.word_id_step
            
        # Split text into words and assign sequential IDs
        words = text.split()
        self.original_words.clear()
        
        for i, word in enumerate(words):
            word_id = (i + 1) * word_id_step
            # Add space after each word except the last one
            word_text = word + (" " if i < len(words) - 1 else "")
            self.original_words[word_id] = word_text
        
        self.expected_next_id = word_id_step
        self.updated_words.clear()
        self.first_change_id = None
    
    def process_word(self, word_id: int, text: str) -> ProcessingResult:
        """
        Process a word update in sequential order.
        
        Args:
            word_id: The word ID
            text: The word text (with spacing)
            
        Returns:
            ProcessingResult indicating what should be emitted
        """
        # Handle mid-stream start: if this is first word and ID > expected, adjust
        # BUT only if we have no original text context OR the word_id is beyond our original text
        max_original_id = max(self.original_words.keys()) if self.original_words else 0
        
        if (self.expected_next_id == self.word_id_step and 
            word_id > self.word_id_step and
            not self.updated_words and
            (not self.original_words or word_id > max_original_id)):
            self.expected_next_id = word_id
        
        # Allow replacements of previously emitted words for streaming mode
        
        # Handle three cases:
        # 1. Sequential new words (word_id == expected_next_id)
        # 2. Replacement of existing words (word_id in updated_words or original_words) 
        # 3. Gap insertion (word_id < expected_next_id but not in existing words)
        is_sequential_new = (word_id == self.expected_next_id)
        is_replacement = (word_id in self.updated_words or word_id in self.original_words)
        is_gap_insertion = (word_id < self.expected_next_id and 
                           word_id not in self.updated_words and 
                           word_id not in self.original_words)
        
        if not (is_sequential_new or is_replacement or is_gap_insertion):
            return ProcessingResult([], 0, False)
        
        # Track if this is a change from original
        original_text = self.original_words.get(word_id, "")
        if text != original_text:
            self.updated_words[word_id] = text
            if self.first_change_id is None or word_id < self.first_change_id:
                self.first_change_id = word_id
        
        # Collect words to emit based on whether this is sequential, replacement, or gap insertion
        words_to_emit = []
        
        if is_replacement or is_gap_insertion:
            # For replacements, emit from first change point to current maximum
            start_id = self.first_change_id if self.first_change_id is not None else word_id
            max_id = max(
                max(self.updated_words.keys(), default=word_id),
                max(self.original_words.keys(), default=word_id)
            )
            
            current_id = start_id
            while current_id <= max_id:
                if current_id == word_id:
                    # The word we just updated
                    words_to_emit.append(DictationWord(id=current_id, text=text))
                elif current_id in self.updated_words:
                    # Previously updated word
                    words_to_emit.append(DictationWord(id=current_id, text=self.updated_words[current_id]))
                elif current_id in self.original_words:
                    # Fill with original content
                    words_to_emit.append(DictationWord(id=current_id, text=self.original_words[current_id]))
                    
                current_id += self.word_id_step
            
            # For replacements, don't change expected_next_id
            
        else:
            # Sequential new word - emit this word + consecutive fillable words
            current_id = word_id
            
            while True:
                if current_id == word_id:
                    # The word we just processed
                    words_to_emit.append(DictationWord(id=current_id, text=text))
                elif current_id in self.updated_words:
                    # Previously updated word
                    words_to_emit.append(DictationWord(id=current_id, text=self.updated_words[current_id]))
                elif current_id in self.original_words:
                    # Fill with original content
                    words_to_emit.append(DictationWord(id=current_id, text=self.original_words[current_id]))
                else:
                    # No more words available
                    break
                    
                current_id += self.word_id_step
            
            # Update expected next ID to after last emitted word
            self.expected_next_id = current_id
        
        # For sequential processing, don't backspace - just emit incremental text
        # For replacements, backspace to the changed word position
        if is_replacement or is_gap_insertion:
            backspace_position = self._calculate_word_position(word_id)
            # For replacements, emit from the changed word forward
            incremental_text = self._get_text_from_word_id(word_id)
        else:
            # Sequential new word - no backspace needed, just emit new content
            backspace_position = self.last_emitted_position
            # Only emit the new words we just added
            incremental_text = ''.join(word.text for word in words_to_emit)
        
        # Update last emitted position
        current_full_text = self.get_text_from_position(0)
        self.last_emitted_position = len(current_full_text)
        
        # Mark all emitted words as processed (reject future updates)
        for word in words_to_emit:
            self.emitted_words[word.id] = word.text
        
        return ProcessingResult(words_to_emit, backspace_position, True, incremental_text)
    
    def _calculate_backspace_position(self) -> int:
        """Calculate character position to backspace to (first change point)."""
        if self.first_change_id is None:
            return 0
            
        return self._calculate_word_position(self.first_change_id)
    
    def _calculate_word_position(self, target_word_id: int) -> int:
        """Calculate character position of a specific word."""
        position = 0
        current_id = self.word_id_step
        
        # Sum lengths up to target word
        while current_id < target_word_id:
            if current_id in self.updated_words:
                position += len(self.updated_words[current_id])
            elif current_id in self.original_words:
                position += len(self.original_words[current_id])
            current_id += self.word_id_step
            
        return position
    
    def get_text_from_position(self, from_position: int = 0) -> str:
        """Get current text starting from a specific character position."""
        full_text = ""
        current_id = self.word_id_step
        
        # Find max ID to iterate to
        max_id = max(
            max(self.original_words.keys(), default=0),
            max(self.updated_words.keys(), default=0)
        )
        
        while current_id <= max_id:
            if current_id in self.updated_words:
                full_text += self.updated_words[current_id]
            elif current_id in self.original_words:
                full_text += self.original_words[current_id]
            current_id += self.word_id_step
            
        return full_text[from_position:]
    
    def _get_text_from_word_id(self, from_word_id: int) -> str:
        """Get text starting from a specific word ID."""
        text = ""
        current_id = from_word_id
        
        # Find max ID to iterate to
        max_id = max(
            max(self.original_words.keys(), default=0),
            max(self.updated_words.keys(), default=0)
        )
        
        while current_id <= max_id:
            if current_id in self.updated_words:
                text += self.updated_words[current_id]
            elif current_id in self.original_words:
                text += self.original_words[current_id]
            current_id += self.word_id_step
            
        return text
    
    def reset(self) -> None:
        """Reset processor to initial state."""
        self.updated_words.clear()
        self.emitted_words.clear()
        self.expected_next_id = self.word_id_step
        self.first_change_id = None
        self.last_emitted_position = 0