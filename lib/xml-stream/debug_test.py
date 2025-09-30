#!/usr/bin/env python3
"""Quick debug script for test values."""

from xml_stream_processor import XMLStreamProcessor
from keyboard_injector import MockKeyboardInjector

def debug_empty_state():
    keyboard = MockKeyboardInjector()
    processor = XMLStreamProcessor(keyboard)
    processor.reset({})
    
    processor.process_chunk("<10>Hello </10>")
    processor.end_stream()
    
    print("Empty state test:")
    print("Operations:", keyboard.operations)
    print("Output:", repr(keyboard.output))
    print()

def debug_replacement_deletion():
    keyboard = MockKeyboardInjector()
    processor = XMLStreamProcessor(keyboard)
    initial_words = {10: "The ", 20: "quick "}
    processor.reset(initial_words)
    
    print("Original string:", repr(''.join(initial_words[k] for k in sorted(initial_words))))
    
    processor.process_chunk("<20>fast </20>")
    print("After first update:", keyboard.operations)
    
    processor.process_chunk("<20></20>")
    print("After deletion:", keyboard.operations)
    print("Output:", repr(keyboard.output))
    print()

def debug_large_numbers():
    keyboard = MockKeyboardInjector()
    processor = XMLStreamProcessor(keyboard)
    initial_words = {1000: "First ", 2000: "Second "}
    processor.reset(initial_words)
    
    original = ''.join(initial_words[k] for k in sorted(initial_words))
    print("Large numbers test:")
    print("Original string:", repr(original), "len:", len(original))
    
    processor.process_chunk("<2000>Last </2000>")
    processor.end_stream()
    
    print("Operations:", keyboard.operations)
    print("Output:", repr(keyboard.output))
    print()

if __name__ == "__main__":
    debug_empty_state()
    debug_replacement_deletion()
    debug_large_numbers()