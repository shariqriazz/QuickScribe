"""
Module for managing conversation state with in-memory word-level XML structure.

This module provides functionality to store and update conversation
history as XML-tagged words where the model has complete control over word IDs.
"""

import html
from dataclasses import dataclass
from typing import Dict


@dataclass
class ConversationState:
    """
    Represents the complete conversation state with XML word tracking.
    
    Attributes:
        words: Dictionary mapping word IDs to their text content
    """
    words: Dict[int, str]
    
    def __init__(self):
        """Initialize empty conversation state."""
        self.words = {}
    
    def update_word(self, word_id: int, text: str) -> None:
        """
        Update or add a word in the conversation.
        
        Args:
            word_id: The word ID from XML tag
            text: The word content (will be unescaped from XML)
        """
        # Unescape XML entities (&amp; &gt; &lt;) 
        unescaped_text = html.unescape(text)
        self.words[word_id] = unescaped_text
    
    def delete_word(self, word_id: int) -> None:
        """
        Delete a word from the conversation.
        
        Args:
            word_id: The word ID to delete
        """
        self.words.pop(word_id, None)
    
    def to_xml(self) -> str:
        """
        Convert conversation state to XML format for API.
        
        Returns:
            XML string with all words: <10>hello</10><20>world</20>...
        """
        if not self.words:
            return ""
        
        sorted_ids = sorted(self.words.keys())
        return ''.join(f'<{word_id}>{self.words[word_id]}</{word_id}>' for word_id in sorted_ids)
    
    def to_text(self) -> str:
        """
        Convert conversation state to plain text (no spaces injected).
        Model has full control over spacing and punctuation.
        
        Returns:
            Concatenated text with model-controlled spacing
        """
        if not self.words:
            return ""
        
        sorted_ids = sorted(self.words.keys())
        return ''.join(self.words[word_id] for word_id in sorted_ids)
    
    def to_text_from_words(self, words: list) -> str:
        """
        Convert list of DictationWord objects to text (no spaces injected).
        Single point of truth for word merging.
        
        Args:
            words: List of DictationWord objects
            
        Returns:
            Concatenated text with model-controlled spacing
        """
        if not words:
            return ""
        
        # Filter out None text (deleted words) and concatenate
        valid_texts = [w.text for w in words if w.text is not None]
        return ''.join(valid_texts)
    
    def clear(self) -> None:
        """Clear all words from conversation."""
        self.words.clear()


class ConversationManager:
    """
    Manages conversation state operations (memory-only).
    """
    
    def __init__(self):
        """Initialize conversation manager with empty state."""
        self.state = ConversationState()
    
    def load_conversation(self) -> ConversationState:
        """
        Return current conversation state (no disk loading).
        
        Returns:
            ConversationState object
        """
        return self.state
    
    def save_conversation(self) -> None:
        """No-op for memory-only conversation state."""
        pass
    
    def reset_conversation(self) -> None:
        """Reset conversation state (memory-only)."""
        self.state.clear()