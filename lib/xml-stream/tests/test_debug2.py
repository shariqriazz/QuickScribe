#!/usr/bin/env python3
"""Debug failing test cases."""

import sys
import os
import pytest

# Add parent directory to path for imports
parent_dir = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, parent_dir)

from xml_stream_processor import XMLStreamProcessor
from keyboard_injector import MockKeyboardInjector

def test_debug_whitespace():
    """Debug whitespace test."""
    keyboard = MockKeyboardInjector()
    processor = XMLStreamProcessor(keyboard)
    initial_words = {10: "Tab\t", 20: "newline\n", 30: "space "}
    processor.reset(initial_words)
    
    original = ''.join(initial_words[k] for k in sorted(initial_words))
    print(f"\nWhitespace debug:")
    print(f"Original: {repr(original)} (len: {len(original)})")
    
    processor.process_chunk("<20>return\r</20>")
    processor.end_stream()
    
    print(f"Operations: {keyboard.operations}")
    print(f"Output: {repr(keyboard.output)}")

def test_debug_malformed():
    """Debug malformed XML test."""
    keyboard = MockKeyboardInjector()
    processor = XMLStreamProcessor(keyboard)
    initial_words = {10: "Hello "}
    processor.reset(initial_words)
    
    original = ''.join(initial_words[k] for k in sorted(initial_words))
    print(f"\nMalformed debug:")
    print(f"Original: {repr(original)} (len: {len(original)})")
    
    processor.process_chunk("<invalid>text</invalid>")
    processor.process_chunk("<10>Hi </10>")
    processor.end_stream()
    
    print(f"Operations: {keyboard.operations}")
    print(f"Output: {repr(keyboard.output)}")
    print(f"Buffer: {repr(processor.xml_buffer)}")