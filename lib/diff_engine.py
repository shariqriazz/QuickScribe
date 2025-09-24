"""
Module for comparing two lists of DictationWord objects and computing
the operations needed to transform one into the other.
"""

from dataclasses import dataclass
from typing import List

from .word_stream import DictationWord
from .conversation_state import ConversationState


@dataclass
class DiffResult:
    """
    Represents the operations needed to transform one text into another.
    
    Attributes:
        backspaces: Number of characters to delete
        new_text: New string to be typed
    """
    backspaces: int
    new_text: str


class DiffEngine:
    """
    Engine for comparing two lists of DictationWord objects and computing
    the difference between them.
    """
    
    def __init__(self):
        """Initialize with conversation state for text merging."""
        self._conversation_state = ConversationState()
    
    @staticmethod
    def _find_divergence_point(old_words: List[DictationWord], 
                             new_words: List[DictationWord]) -> int:
        """Find the index where the two lists first differ."""
        for i in range(min(len(old_words), len(new_words))):
            # Compare both ID and text, treating None text as different from any string
            if (old_words[i].id != new_words[i].id or 
                old_words[i].text != new_words[i].text):
                return i
        return min(len(old_words), len(new_words))

    def _calculate_text_length(self, words: List[DictationWord], start_idx: int) -> int:
        """Calculate total length of text with model-controlled spacing."""
        if not words[start_idx:]:
            return 0

        # Use single point of truth for text merging
        text = self._conversation_state.to_text_from_words(words[start_idx:])
        return len(text)

    def _join_words(self, words: List[DictationWord], start_idx: int) -> str:
        """Join words with model-controlled spacing."""
        if not words[start_idx:]:
            return ""

        # Use single point of truth for text merging
        return self._conversation_state.to_text_from_words(words[start_idx:])

    def compare(self, old_words: List[DictationWord], new_words: List[DictationWord]) -> DiffResult:
        """
        Compare two lists of DictationWord objects and compute the difference.
        
        Args:
            old_words: Original list of DictationWord objects
            new_words: New list of DictationWord objects to compare against
        
        Returns:
            DiffResult containing the number of backspaces needed and the new text
            to be typed to transform old_words into new_words
        """
        if not old_words and not new_words:
            return DiffResult(backspaces=0, new_text="")
            
        divergence_idx = self._find_divergence_point(old_words, new_words)
        
        # Calculate backspaces needed to erase old text from divergence point
        backspaces = self._calculate_text_length(old_words, divergence_idx)
        
        # Get new text to be typed from divergence point
        new_text = self._join_words(new_words, divergence_idx)
        
        return DiffResult(backspaces=backspaces, new_text=new_text)