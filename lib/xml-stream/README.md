# XML Stream Sequential Word Processing

A Python library for processing XML-tagged word updates that arrive sequentially from AI transcription services. Handles real-time text modifications with minimal backspacing and gap filling for optimal user experience.

## Overview

This library processes streaming XML updates like `<10>word</10>` where numbers represent sequential word positions. It calculates minimal backspace operations and emits corrected text through a keyboard injection interface.

## Quick Start

```python
from xml_stream_processor import XMLStreamProcessor
from keyboard_injector import MockKeyboardInjector

# Create processor with keyboard injector
keyboard = MockKeyboardInjector()
processor = XMLStreamProcessor(keyboard)

# Initialize with baseline word mapping
initial_words = {10: "The ", 20: "quick ", 30: "brown ", 40: "fox "}
processor.reset(initial_words)

# Process XML chunks as they arrive
processor.process_chunk("<20>fast </20>")
processor.process_chunk("<40>dog </40>")

# Signal end of stream
processor.end_stream()

print(keyboard.output)  # "The fast brown dog "
```

## Core Components

### XMLStreamProcessor

Main processor that handles XML parsing, backspace calculation, and emission sequencing.

```python
class XMLStreamProcessor:
    def __init__(self, keyboard: KeyboardInjector)
    def reset(self, words: Dict[int, str]) -> None
    def process_chunk(self, chunk: str) -> None
    def end_stream(self) -> None
```

### KeyboardInjector Interface

Abstract interface for keyboard operations:

```python
class KeyboardInjector(ABC):
    @abstractmethod
    def bksp(self, count: int) -> None    # Backspace count characters
    
    @abstractmethod 
    def emit(self, text: str) -> None     # Emit text at cursor
```

## Usage Patterns

### Basic Word Replacement

```python
initial_words = {10: "Hello ", 20: "world "}
processor.reset(initial_words)

processor.process_chunk("<20>universe </20>")
processor.end_stream()

# Result: "Hello universe "
```

### XML Fragmentation Handling

XML tags can be split across chunks arbitrarily:

```python
processor.process_chunk("<1")
processor.process_chunk("0>Hi ")
processor.process_chunk("</10>")

# Processes complete tag when closing tag arrives
```

### Word Deletion

Empty XML tags delete words from the sequence:

```python
initial_words = {10: "The ", 20: "quick ", 30: "fox "}
processor.reset(initial_words)

processor.process_chunk("<20></20>")  # Delete word 20
processor.end_stream()

# Result: "The fox "
```

### Gap Filling

Missing sequences are filled with unchanged words:

```python
initial_words = {10: "I ", 20: "will ", 30: "go ", 40: "home "}
processor.reset(initial_words)

processor.process_chunk("<20>might </20>")
processor.process_chunk("<40>there </40>")
processor.end_stream()

# Automatically fills gap with word 30: "I might go there "
```

### Multiple Operations

Process multiple updates in single chunk:

```python
processor.process_chunk("<10>A </10><20>fast </20><30>red </30>")
```

## Implementation Details

### Backspace Calculation

On first update, calculates minimal backspace by comparing original and modified strings:

1. Build original string from word dictionary
2. Create modified version with update applied  
3. Find common prefix length
4. Backspace: `len(original) - prefix_length`

### Sequential Processing

- Updates always arrive in sequential order (10, 20, 30...)
- May skip unchanged words (10, 30, 50...)
- Gap filling emits skipped words from original mapping
- Subsequent updates only require emission, no backspace

### Stream Lifecycle

1. **Initialization**: `reset(initial_words)` sets baseline
2. **Processing**: `process_chunk()` handles XML fragments
3. **Termination**: `end_stream()` emits remaining unchanged words
4. **Reset**: New transcription session with different baseline

## Error Handling

- **Malformed XML**: Invalid tags ignored, processing continues
- **Partial Tags**: Buffered until complete tag received
- **Missing Sequences**: Gaps filled automatically
- **Empty State**: Handles empty initial word mapping

## Unicode Support

Full Unicode support including emojis and multi-byte characters:

```python
initial_words = {10: "Hello ", 20: "世界 "}
processor.process_chunk("<20>🌍 </20>")
# Handles Unicode correctly in backspace calculations
```

## Testing

Run comprehensive test suite:

```bash
python -m pytest test_xml_stream_processor.py -v
```

Tests cover:
- Basic functionality and edge cases  
- XML fragmentation across chunks
- Gap filling and deletion logic
- Unicode and whitespace preservation
- State management and lifecycle

## Integration Example

For integration with xdotool:

```python
from keyboard_injector import KeyboardInjector
import subprocess

class XdotoolKeyboardInjector(KeyboardInjector):
    def bksp(self, count: int) -> None:
        if count > 0:
            subprocess.run(['xdotool', 'key', '--repeat', str(count), 'BackSpace'])
    
    def emit(self, text: str) -> None:
        if text:
            subprocess.run(['xdotool', 'type', text])

# Use with processor
keyboard = XdotoolKeyboardInjector()
processor = XMLStreamProcessor(keyboard)
```

## Performance Characteristics

- **Memory**: O(n) where n is number of words in baseline
- **Processing**: O(1) per XML tag after first backspace calculation
- **Backspace**: Only calculated once on first update
- **Gap Filling**: O(k) where k is number of gaps to fill