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
            self._process_single_update(seq, word)
    
    def end_stream(self) -> None:
        """Flush remaining chunks from last_emitted_seq to end."""
        if self.backspace_performed:
            # Emit all remaining chunks
            max_seq = max(self.current_words.keys()) if self.current_words else 0
            if max_seq > self.last_emitted_seq:
                self._emit_up_to_sequence(max_seq)

        # Clear buffer
        self.xml_buffer = ""
    
    def _extract_complete_tags(self, buffer: str) -> Tuple[List[Tuple[int, str]], str]:
        """Extract complete <N>word</N> tags, return remaining buffer."""
        pattern = r'<(\d+)>(.*?)</\1>'
        updates = []
        last_end = 0
        
        print(f"      _extract_complete_tags(buffer='{buffer}')")
        
        for match in re.finditer(pattern, buffer):
            seq = int(match.group(1))
            word = match.group(2)
            updates.append((seq, word))
            last_end = match.end()
            print(f"        Found complete tag: seq={seq}, word='{word}'")
        
        # Return remaining buffer after last complete match
        remaining_buffer = buffer[last_end:]
        print(f"        Remaining buffer: '{remaining_buffer}'")
        print(f"        Returning updates: {updates}")
        return updates, remaining_buffer
    
    def _process_single_update(self, seq: int, word: str) -> None:
        """Process individual word update with incremental emission."""
        print(f"        _process_single_update(seq={seq}, word='{word}')")
        print(f"          current_words[{seq}] = '{self.current_words.get(seq, '<MISSING>')}'")
        is_changed = word != self.current_words.get(seq, "")
        print(f"          is_changed = {is_changed}")
        print(f"          backspace_performed = {self.backspace_performed}")

        # Check if we need to backspace for the first change in this batch
        need_backspace = is_changed and not self.backspace_performed

        # Special case: if this change is before last_emitted_seq, we need to backspace even if backspace_performed
        if is_changed and self.backspace_performed and seq <= self.last_emitted_seq:
            print(f"          -> change before last_emitted_seq ({self.last_emitted_seq}), need new backspace")
            need_backspace = True
            # Reset backspace flag for this new batch of changes
            self.backspace_performed = False

        if need_backspace:
            # First change: backspace to this chunk's boundary
            print(f"          -> first change detected, performing backspace")
            backspace_count = self._calculate_backspace_count(seq)
            print(f"          -> backspace_count: {backspace_count}")
            self._perform_backspace(backspace_count)
            self.backspace_performed = True
            # Reset last_emitted_seq since we backspaced
            self.last_emitted_seq = seq - 1 if seq > 1 else 0

        # Update the word
        self.current_words[seq] = word

        if self.backspace_performed:
            # Emit up to this sequence
            print(f"          -> emitting up to sequence {seq}")
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
            print(f"            ⌫ BACKSPACE({count})")
            self.keyboard.bksp(count)
            self.backspace_performed = True
        else:
            print(f"            ⚪ NO BACKSPACE NEEDED")

    def _emit_up_to_sequence(self, target_seq: int) -> None:
        """Emit all chunks from last_emitted_seq+1 to target_seq (filling gaps)."""
        print(f"          _emit_up_to_sequence(target_seq={target_seq})")
        print(f"            last_emitted_seq: {self.last_emitted_seq}")

        # Find all sequences to emit
        seqs_to_emit = sorted(k for k in self.current_words.keys()
                             if self.last_emitted_seq < k <= target_seq)
        print(f"            seqs_to_emit: {seqs_to_emit}")

        # Emit each chunk in order
        for seq in seqs_to_emit:
            word = self.current_words[seq]
            print(f"            📝 EMIT('{word}') for seq={seq}")
            self.keyboard.emit(word)

        # Update last emitted sequence
        if seqs_to_emit:
            self.last_emitted_seq = max(seqs_to_emit)
            print(f"            ➡️  last_emitted_seq = {self.last_emitted_seq}")
    
    def _build_string_from_words(self, words: Dict[int, str]) -> str:
        """Build complete string from word dictionary."""
        if not words:
            return ""
        return ''.join(words[k] for k in sorted(words.keys()))
    
