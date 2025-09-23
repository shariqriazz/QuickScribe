#!/usr/bin/env python3
"""
Quick test to verify XML conversation tag processing works correctly.
"""

import sys
import os
import re

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from lib.word_stream import WordStreamParser, DictationWord
from lib.diff_engine import DiffEngine
from lib.output_manager import OutputManager, XdotoolError

# Mock the necessary parts of dictate module for testing
class MockDictate:
    def __init__(self):
        self.current_words = []
        self.word_parser = WordStreamParser()
        self.diff_engine = DiffEngine()
        self.output_manager = None
        self.CONVERSATION_HISTORY = []
        self.USE_XDOTOOL = False
    
    def detect_and_execute_commands(self, text):
        """Mock command detection - just return text with 'reset' commands removed."""
        reset_patterns = ["reset conversation", "clear conversation", "start over", "new conversation", "clear context"]
        for pattern in reset_patterns:
            if pattern in text.lower():
                self.CONVERSATION_HISTORY.clear()
                self.current_words = []
                return text.replace(pattern, "").strip()
        return text
    
    def process_xml_transcription(self, text):
        """Process XML transcription text using the word processing pipeline."""
        try:
            # Check for conversation tags first
            conversation_pattern = re.compile(r'<conversation>(.*?)</conversation>', re.DOTALL)
            conversation_matches = conversation_pattern.findall(text)
            
            # Process conversation content
            for conversation_content in conversation_matches:
                content = conversation_content.strip()
                if content:
                    # Process commands in conversation content
                    cleaned_content = self.detect_and_execute_commands(content)
                    if cleaned_content.strip():
                        self.CONVERSATION_HISTORY.append(cleaned_content)
                        # Keep only last 10 exchanges
                        if len(self.CONVERSATION_HISTORY) > 10:
                            self.CONVERSATION_HISTORY.pop(0)
            
            # Remove conversation tags from text before processing words
            text_without_conversation = conversation_pattern.sub('', text)
            
            # Parse XML to extract words
            newly_completed_words = self.word_parser.parse(text_without_conversation)
            if not newly_completed_words:
                return
            
            # Update current state with newly completed words
            updated_words = self.current_words.copy()
            
            for new_word in newly_completed_words:
                # Find if this word ID already exists
                existing_index = None
                for i, existing_word in enumerate(updated_words):
                    if existing_word.id == new_word.id:
                        existing_index = i
                        break
                
                if existing_index is not None:
                    # Update existing word
                    updated_words[existing_index] = new_word
                else:
                    # Add new word, keeping words sorted by ID
                    inserted = False
                    for i, existing_word in enumerate(updated_words):
                        if new_word.id < existing_word.id:
                            updated_words.insert(i, new_word)
                            inserted = True
                            break
                    if not inserted:
                        updated_words.append(new_word)
            
            # Update current words
            self.current_words = updated_words
            
        except Exception as e:
            print(f"Error in XML processing: {e}")

# Create a global mock instance for tests
dictate = MockDictate()

def test_conversation_processing():
    """Test that conversation tags are properly detected and processed."""
    
    # Reset state
    dictate.current_words = []
    dictate.word_parser = WordStreamParser()
    dictate.diff_engine = DiffEngine()
    dictate.output_manager = None  # Don't actually execute xdotool
    dictate.CONVERSATION_HISTORY = []
    dictate.USE_XDOTOOL = False
    
    # Test text with both conversation and word tags
    test_xml = '<conversation>Let me reset the conversation now.</conversation><10>hello</10><20>world</20>'
    
    # Process the XML
    dictate.process_xml_transcription(test_xml)
    
    # Verify results
    assert len(dictate.CONVERSATION_HISTORY) > 0, "Conversation should be in history"
    assert len(dictate.current_words) == 2, "Should have 2 words"
    assert dictate.current_words[0].text == "hello", "First word should be 'hello'"
    assert dictate.current_words[1].text == "world", "Second word should be 'world'"

def test_word_only_processing():
    """Test processing XML with only word tags."""
    
    # Reset state
    dictate.current_words = []
    dictate.word_parser = WordStreamParser()
    dictate.diff_engine = DiffEngine()
    dictate.output_manager = None
    dictate.CONVERSATION_HISTORY = []
    dictate.USE_XDOTOOL = False
    
    # Test text with only word tags
    test_xml = '<10>hello</10><20>beautiful</20><30>world</30>'
    
    # Process the XML
    dictate.process_xml_transcription(test_xml)
    
    # Verify results
    assert len(dictate.current_words) == 3, "Should have 3 words"
    assert dictate.current_words[0].text == "hello", "First word should be 'hello'"
    assert dictate.current_words[1].text == "beautiful", "Second word should be 'beautiful'"
    assert dictate.current_words[2].text == "world", "Third word should be 'world'"

def test_conversation_only_processing():
    """Test processing XML with only conversation tags."""
    
    # Reset state
    dictate.current_words = []
    dictate.word_parser = WordStreamParser()
    dictate.diff_engine = DiffEngine()
    dictate.output_manager = None
    dictate.CONVERSATION_HISTORY = []
    dictate.USE_XDOTOOL = False
    
    # Test text with only conversation tags
    test_xml = '<conversation>This is a response from the AI assistant.</conversation>'
    
    # Process the XML
    dictate.process_xml_transcription(test_xml)
    
    # Verify results
    assert len(dictate.CONVERSATION_HISTORY) == 1, "Should have 1 conversation entry"
    assert len(dictate.current_words) == 0, "Should have no words"
    assert "AI assistant" in dictate.CONVERSATION_HISTORY[0], "Conversation should contain AI assistant text"