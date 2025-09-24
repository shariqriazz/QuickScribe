"""
Module for parsing a stream of XML-like fragments representing dictated words.

This module provides functionality to parse a stream of XML-like fragments
in the format <id>word</id>, handling incomplete or partial tags gracefully
in a real-time streaming environment.
"""

import re
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class DictationWord:
    """
    Represents a parsed word from the dictation stream.
    
    Attributes:
        id: The numeric ID from the XML tag
        text: The word content from the XML tag, or None for deletion
    """
    id: int
    text: Optional[str]


class WordStreamParser:
    """
    Parser for a stream of XML-like fragments representing dictated words.
    
    This parser handles incomplete or partial XML tags, which are expected
    in a real-time streaming environment. It accumulates data and only
    processes fully-formed tags.
    """
    
    def __init__(self):
        """Initialize the parser with an empty buffer."""
        self._buffer = ""
        # Regex pattern to match complete tags: <id>word</id>
        # The pattern captures the id and the word content
        # Using re.DOTALL to make . match newlines as well
        self._pattern = re.compile(r'<(\d+)>(.*?)</\1>', re.DOTALL)
    
    def parse(self, chunk: str) -> List[DictationWord]:
        """
        Parse a chunk of text from the stream.
        
        Args:
            chunk: A string chunk from the stream, which may contain
                  complete or partial XML-like tags.
        
        Returns:
            A list of DictationWord objects extracted from the chunk.
        """
        # Check if this is the new format with <x><update>...</update></x>
        update_pattern = re.compile(r'<update>(.*?)</update>', re.DOTALL)
        update_match = update_pattern.search(chunk)
        
        if update_match:
            # Extract content from <update> section and parse it
            update_content = update_match.group(1)
            self._buffer += update_content
        else:
            # Old format - append the chunk directly
            self._buffer += chunk
        
        # Find all complete tags in the buffer
        words = []
        
        # Find all matches in the current buffer
        matches = list(self._pattern.finditer(self._buffer))
        
        if not matches:
            # No complete tags found - check if buffer contains potential incomplete XML
            xml_pattern = re.compile(r'<[^>]*$')  # Incomplete opening tag at end
            if xml_pattern.search(self._buffer):
                # Keep potential incomplete XML tag
                pass  # Keep buffer as is
            else:
                # Discard non-XML content (whitespace, text, etc.)
                self._buffer = ""
            return words
        
        # Process all complete matches
        last_end = 0

        for match in matches:
            try:
                # Extract the word from the match
                word_id = int(match.group(1))
                word_text = match.group(2)
                
                # Always store the text content (empty string is valid)
                # None is reserved for explicit deletions (handled elsewhere)
                words.append(DictationWord(id=word_id, text=word_text))
                    
                last_end = match.end()
            except (ValueError, IndexError):
                # Skip invalid matches (shouldn't happen with our regex)
                continue

        # Keep only unprocessed content (potential incomplete XML tags)
        # Discard all non-XML text - only <N>...</N> content matters
        remaining = self._buffer[last_end:] if last_end < len(self._buffer) else ""
        
        # Filter out any non-XML text, keep only potential incomplete tags
        # Keep only text that looks like it could be part of an XML tag
        xml_pattern = re.compile(r'<[^>]*$')  # Incomplete opening tag at end
        if xml_pattern.search(remaining):
            self._buffer = remaining
        else:
            self._buffer = ""
        
        return words
    
    def get_buffer(self) -> str:
        """
        Get the current buffer content.
        
        This method is primarily for testing and debugging purposes.
        
        Returns:
            The current content of the internal buffer.
        """
        return self._buffer
    
    def clear_buffer(self) -> None:
        """
        Clear the internal buffer.
        
        This method can be used to reset the parser state.
        """
        self._buffer = ""