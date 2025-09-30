#!/usr/bin/env python3
"""Debug tests to determine correct expected values."""

import pytest
from xml_stream_processor import XMLStreamProcessor
from keyboard_injector import MockKeyboardInjector

def test_debug_empty_state():
    """Debug test for empty initial state."""
    keyboard = MockKeyboardInjector()
    processor = XMLStreamProcessor(keyboard)
    processor.reset({})
    
    processor.process_chunk("<10>Hello </10>")
    processor.end_stream()
    
    print(f"\nEmpty state debug:")
    print(f"Operations: {keyboard.operations}")
    print(f"Output: {repr(keyboard.output)}")

def test_debug_replacement_deletion():
    """Debug test for replacement then deletion."""
    keyboard = MockKeyboardInjector()
    processor = XMLStreamProcessor(keyboard)
    initial_words = {10: "The ", 20: "quick "}
    processor.reset(initial_words)
    
    original = ''.join(initial_words[k] for k in sorted(initial_words))
    print(f"\nReplacement/deletion debug:")
    print(f"Original string: {repr(original)} (len: {len(original)})")
    
    processor.process_chunk("<20>fast </20>")
    print(f"After replacement: {keyboard.operations}")
    
    processor.process_chunk("<20></20>")
    print(f"After deletion: {keyboard.operations}")
    print(f"Final output: {repr(keyboard.output)}")

def test_debug_large_numbers():
    """Debug test for large sequence numbers."""
    keyboard = MockKeyboardInjector()
    processor = XMLStreamProcessor(keyboard)
    initial_words = {1000: "First ", 2000: "Second "}
    processor.reset(initial_words)
    
    original = ''.join(initial_words[k] for k in sorted(initial_words))
    print(f"\nLarge numbers debug:")
    print(f"Original string: {repr(original)} (len: {len(original)})")
    
    processor.process_chunk("<2000>Last </2000>")
    processor.end_stream()
    
    print(f"Operations: {keyboard.operations}")
    print(f"Output: {repr(keyboard.output)}")

def test_debug_mixed_operations():
    """Debug test for mixed operations in single chunk."""
    keyboard = MockKeyboardInjector()
    processor = XMLStreamProcessor(keyboard)
    initial_words = {10: "The ", 20: "quick ", 30: "brown ", 40: "fox "}
    processor.reset(initial_words)
    
    original = ''.join(initial_words[k] for k in sorted(initial_words))
    print(f"\nMixed operations debug:")
    print(f"Original string: {repr(original)} (len: {len(original)})")
    
    processor.process_chunk("<10>A </10><20></20><30>red </30>")
    processor.end_stream()
    
    print(f"Operations: {keyboard.operations}")
    print(f"Output: {repr(keyboard.output)}")