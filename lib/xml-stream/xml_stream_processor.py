"""XML Stream Sequential Word Processing Implementation."""

import re
import sys
from typing import Dict, List, Tuple

from keyboard_injector import KeyboardInjector


class XMLStreamProcessor:
    """Processes XML-tagged word updates arriving in sequential order."""
    
    def __init__(self, keyboard: KeyboardInjector, debug_enabled: bool = False):
        self.keyboard = keyboard
        self.current_words: Dict[int, str] = {}
        self.xml_buffer: str = ""
        self.backspace_performed: bool = False
        self.last_emitted_seq: int = 0

        # Debug system
        self.debug_enabled = debug_enabled
        self.debug_buffer: List[str] = []
        self.streaming_active: bool = False
    
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
            self._process_single_update(seq, word)
    
    def end_stream(self) -> None:
        """Flush remaining chunks from last_emitted_seq to end."""
        if self.backspace_performed:
            # Emit all remaining chunks
            max_seq = max(self.current_words.keys()) if self.current_words else 0
            if max_seq > self.last_emitted_seq:
                self._emit_up_to_sequence(max_seq)

        # Mark end of streaming and flush debug if enabled
        self.streaming_active = False
        if self.debug_enabled:
            self._flush_debug_buffer()

        # Clear buffer
        self.xml_buffer = ""

    def _debug(self, message: str) -> None:
        """Buffer debug messages during streaming, show immediately if not streaming."""
        if self.streaming_active:
            self.debug_buffer.append(message)
        elif self.debug_enabled:
            print(message, file=sys.stderr)

    def _flush_debug_buffer(self) -> None:
        """Flush all buffered debug messages to stderr."""
        if self.debug_buffer:
            print("\n=== DEBUG TRACE ===", file=sys.stderr)
            for message in self.debug_buffer:
                print(message, file=sys.stderr)
            print("=== END DEBUG ===\n", file=sys.stderr)
            self.debug_buffer.clear()

    def start_stream(self) -> None:
        """Mark start of streaming - buffer debug messages."""
        self.streaming_active = True
        self.debug_buffer.clear()
    
    def _unescape_xml_entities(self, text: str) -> str:
        """Unescape XML entities in tag content."""
        text = text.replace('&amp;', '&')
        text = text.replace('&lt;', '<')
        text = text.replace('&gt;', '>')
        return text

    def _extract_complete_tags(self, buffer: str) -> Tuple[List[Tuple[int, str]], str]:
        """Extract complete <N>word</N> tags, return remaining buffer."""
        pattern = r'<(\d+)>(.*?)</\1>'
        updates = []
        last_end = 0

        self._debug(f"      _extract_complete_tags(buffer='{buffer}')")

        for match in re.finditer(pattern, buffer):
            seq = int(match.group(1))
            word = match.group(2)
            # Unescape XML entities in tag content
            word = self._unescape_xml_entities(word)
            updates.append((seq, word))
            last_end = match.end()
            self._debug(f"        Found complete tag: seq={seq}, word='{word}')")

        # Return remaining buffer after last complete match
        remaining_buffer = buffer[last_end:]
        self._debug(f"        Remaining buffer: '{remaining_buffer}')")
        self._debug(f"        Returning updates: {updates}")
        return updates, remaining_buffer
    
    def _process_single_update(self, seq: int, word: str) -> None:
        """Process individual word update with incremental emission."""
        self._debug(f"        _process_single_update(seq={seq}, word='{word}')")
        self._debug(f"          current_words[{seq}] = '{self.current_words.get(seq, '<MISSING>')}'")
        is_changed = word != self.current_words.get(seq, "")
        self._debug(f"          is_changed = {is_changed}")
        self._debug(f"          backspace_performed = {self.backspace_performed}")

        # Check if we need to backspace for the first change in this batch
        need_backspace = is_changed and not self.backspace_performed

        # Special case: if this change is before last_emitted_seq, we need to backspace even if backspace_performed
        if is_changed and self.backspace_performed and seq <= self.last_emitted_seq:
            self._debug(f"          -> change before last_emitted_seq ({self.last_emitted_seq}), need new backspace")
            need_backspace = True
            # Reset backspace flag for this new batch of changes
            self.backspace_performed = False

        if need_backspace:
            # First change: backspace to this chunk's boundary
            self._debug(f"          -> first change detected, performing backspace")
            backspace_count = self._calculate_backspace_count(seq)
            self._debug(f"          -> backspace_count: {backspace_count}")
            self._perform_backspace(backspace_count)
            self.backspace_performed = True
            # Reset last_emitted_seq since we backspaced
            self.last_emitted_seq = seq - 1 if seq > 1 else 0

        # Update the word
        self.current_words[seq] = word

        if self.backspace_performed:
            # Emit up to this sequence
            self._debug(f"          -> emitting up to sequence {seq}")
            self._emit_up_to_sequence(seq)
    
    def _calculate_backspace_count(self, first_changed_seq: int) -> int:
        """Calculate number of characters to backspace to chunk boundary."""
        # Calculate position where first changed chunk starts
        chunk_start = 0
        for seq in sorted(self.current_words.keys()):
            if seq < first_changed_seq:
                chunk_start += len(self.current_words[seq])
            else:
                break

        # Backspace from end to chunk boundary
        current_length = len(self._build_string_from_words(self.current_words))
        return current_length - chunk_start

    def _perform_backspace(self, count: int) -> None:
        """Execute keyboard backspace operation."""
        if count > 0:
            self._debug(f"            ⌫ BACKSPACE({count})")
            self.keyboard.bksp(count)
            self.backspace_performed = True
        else:
            self._debug(f"            ⚪ NO BACKSPACE NEEDED")

    def _emit_up_to_sequence(self, target_seq: int) -> None:
        """Emit all chunks from last_emitted_seq+1 to target_seq (filling gaps)."""
        self._debug(f"          _emit_up_to_sequence(target_seq={target_seq})")
        self._debug(f"            last_emitted_seq: {self.last_emitted_seq}")

        # Find all sequences to emit
        seqs_to_emit = sorted(k for k in self.current_words.keys()
                             if self.last_emitted_seq < k <= target_seq)
        self._debug(f"            seqs_to_emit: {seqs_to_emit}")

        # Emit each chunk in order
        for seq in seqs_to_emit:
            word = self.current_words[seq]
            self._debug(f"            📝 EMIT('{word}') for seq={seq}")
            self.keyboard.emit(word)

        # Update last emitted sequence
        if seqs_to_emit:
            self.last_emitted_seq = max(seqs_to_emit)
            self._debug(f"            ➡️  last_emitted_seq = {self.last_emitted_seq}")
    
    def _build_string_from_words(self, words: Dict[int, str]) -> str:
        """Build complete string from word dictionary."""
        if not words:
            return ""
        return ''.join(words[k] for k in sorted(words.keys()))
    
