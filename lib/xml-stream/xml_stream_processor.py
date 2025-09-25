"""XML Stream Sequential Word Processing Implementation."""

import re
from typing import Dict, List, Tuple

from keyboard_injector import KeyboardInjector


class XMLStreamProcessor:
    """Processes XML-tagged word updates arriving in sequential order."""
    
    def __init__(self, keyboard: KeyboardInjector):
        self.keyboard = keyboard
        self.current_words: Dict[int, str] = {}
        self.xml_buffer: str = ""
        self.backspace_performed: bool = False
        self.last_emitted_seq: int = 0
    
    def reset(self, words: Dict[int, str]) -> None:
        """Initialize with new word mapping for new transcription session."""
        self.current_words = words.copy()
        self.xml_buffer = ""
        self.backspace_performed = False
        self.last_emitted_seq = 0
    
    def process_chunk(self, chunk: str) -> None:
        """Process XML chunk, handling fragments across boundaries."""
        self.xml_buffer += chunk
        
        # Extract all complete tags
        updates, self.xml_buffer = self._extract_complete_tags(self.xml_buffer)
        
        # Process each update
        for seq, word in updates:
            self._process_update(seq, word)
    
    def end_stream(self) -> None:
        """Emit remaining words if backspace was performed, clear buffer."""
        if self.backspace_performed:
            # Emit all remaining words after last_emitted_seq
            remaining_seqs = sorted(k for k in self.current_words.keys() 
                                  if k > self.last_emitted_seq)
            for seq in remaining_seqs:
                self.keyboard.emit(self.current_words[seq])
        
        # Clear buffer regardless
        self.xml_buffer = ""
    
    def _extract_complete_tags(self, buffer: str) -> Tuple[List[Tuple[int, str]], str]:
        """Extract complete <N>word</N> tags, return remaining buffer."""
        pattern = r'<(\d+)>(.*?)</\1>'
        updates = []
        last_end = 0
        
        for match in re.finditer(pattern, buffer):
            seq = int(match.group(1))
            word = match.group(2)
            updates.append((seq, word))
            last_end = match.end()
        
        # Return remaining buffer after last complete match
        remaining_buffer = buffer[last_end:]
        return updates, remaining_buffer
    
    def _process_update(self, seq: int, word: str) -> None:
        """Process individual word update with gap filling."""
        if not self.backspace_performed:
            # First update - calculate backspace
            self._perform_initial_backspace(seq, word)
        else:
            # Subsequent updates - fill gaps and emit
            self._fill_gaps_and_emit(seq, word)
    
    def _perform_initial_backspace(self, seq: int, word: str) -> None:
        """Calculate and perform backspace on first update."""
        # Build original and modified strings
        original_str = self._build_string_from_words(self.current_words)
        
        modified_words = self.current_words.copy()
        if word:  # Non-empty update
            modified_words[seq] = word
        else:  # Empty update - delete
            if seq in modified_words:
                del modified_words[seq]
        
        modified_str = self._build_string_from_words(modified_words)
        
        # Calculate common prefix
        prefix_len = self._find_common_prefix_length(original_str, modified_str)
        backspace_count = len(original_str) - prefix_len
        
        # Perform backspace
        if backspace_count > 0:
            self.keyboard.bksp(backspace_count)
            self.backspace_performed = True
        
        # Update state and emit if non-empty
        if word:  # Non-empty update
            self.current_words[seq] = word
            self.keyboard.emit(word)
        else:  # Empty update - delete
            if seq in self.current_words:
                del self.current_words[seq]
        
        self.last_emitted_seq = seq
    
    def _fill_gaps_and_emit(self, seq: int, word: str) -> None:
        """Fill gaps between last emitted and current sequence, then emit update."""
        # Fill gaps - emit existing words between last_emitted_seq and seq
        gap_seqs = sorted(k for k in self.current_words.keys() 
                         if self.last_emitted_seq < k < seq)
        for gap_seq in gap_seqs:
            self.keyboard.emit(self.current_words[gap_seq])
        
        # Apply update
        if word:  # Non-empty update
            self.current_words[seq] = word
            self.keyboard.emit(word)
        else:  # Empty update - delete
            if seq in self.current_words:
                del self.current_words[seq]
            # No emission for deletions
        
        self.last_emitted_seq = seq
    
    def _build_string_from_words(self, words: Dict[int, str]) -> str:
        """Build complete string from word dictionary."""
        if not words:
            return ""
        return ''.join(words[k] for k in sorted(words.keys()))
    
    def _find_common_prefix_length(self, str1: str, str2: str) -> int:
        """Find length of common prefix between two strings."""
        min_len = min(len(str1), len(str2))
        for i in range(min_len):
            if str1[i] != str2[i]:
                return i
        return min_len