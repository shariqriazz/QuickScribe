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
        self.pending_updates: Dict[int, str] = {}
    
    def reset(self, words: Dict[int, str]) -> None:
        """Initialize with new word mapping for new transcription session."""
        self.current_words = words.copy()
        self.xml_buffer = ""
        self.backspace_performed = False
        self.last_emitted_seq = 0
        self.pending_updates = {}
    
    def process_chunk(self, chunk: str) -> None:
        """Process XML chunk, handling fragments across boundaries."""
        self.xml_buffer += chunk

        # Extract all complete tags
        updates, self.xml_buffer = self._extract_complete_tags(self.xml_buffer)

        # Process each update
        for seq, word in updates:
            self._process_single_update(seq, word)
    
    def end_stream(self) -> None:
        """Flush any pending updates and emit remaining words, clear buffer."""
        if not self.backspace_performed and self.pending_updates:
            # Execute backspace and emit pending updates
            self._execute_backspace_and_emit()
        elif self.backspace_performed:
            # Emit all remaining words after last_emitted_seq
            remaining_seqs = sorted(k for k in self.current_words.keys()
                                  if k > self.last_emitted_seq)
            for seq in remaining_seqs:
                self.keyboard.emit(self.current_words[seq])

        # Clear buffer and pending updates
        self.xml_buffer = ""
        self.pending_updates = {}
    
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
        """Process individual word update with immediate emission or pending."""
        print(f"        _process_single_update(seq={seq}, word='{word}')")
        print(f"          current_words[{seq}] = '{self.current_words.get(seq, '<MISSING>')}'")
        print(f"          is_changed = {word != self.current_words.get(seq, '')}")
        print(f"          backspace_performed = {self.backspace_performed}")

        if not self.backspace_performed:
            # Add to pending and check if we should execute backspace
            print(f"          -> adding to pending updates")
            self.pending_updates[seq] = word
            if self._has_actual_change():
                print(f"          -> executing backspace and emit")
                self._execute_backspace_and_emit()
        else:
            # After backspace, emit immediately with gap filling
            print(f"          -> calling _emit_word_with_gap_fill")
            self._emit_word_with_gap_fill(seq, word)
    
    def _has_actual_change(self) -> bool:
        """Check if pending updates contain any actual changes."""
        for seq, word in self.pending_updates.items():
            if word != self.current_words.get(seq, ""):
                return True
        return False

    def _calculate_backspace_count(self, target_words: Dict[int, str]) -> int:
        """Calculate number of characters to backspace."""
        original_str = self._build_string_from_words(self.current_words)
        target_str = self._build_string_from_words(target_words)
        prefix_len = self._find_common_prefix_length(original_str, target_str)
        return len(original_str) - prefix_len

    def _perform_backspace(self, count: int) -> None:
        """Execute keyboard backspace operation."""
        if count > 0:
            print(f"            ⌫ BACKSPACE({count})")
            self.keyboard.bksp(count)
            self.backspace_performed = True
        else:
            print(f"            ⚪ NO BACKSPACE NEEDED")

    def _execute_backspace_and_emit(self) -> None:
        """Execute backspace calculation and emit all pending updates."""
        print(f"          _execute_backspace_and_emit()")

        # Build target state with pending updates
        target_words = self.current_words.copy()
        for seq, word in self.pending_updates.items():
            if word:  # Non-empty update
                target_words[seq] = word
            else:  # Empty update - delete
                if seq in target_words:
                    del target_words[seq]

        original_str = self._build_string_from_words(self.current_words)
        target_str = self._build_string_from_words(target_words)

        print(f"            original_str: '{original_str}' (len={len(original_str)})")
        print(f"            target_str: '{target_str}' (len={len(target_str)})")

        # Calculate and perform backspace
        backspace_count = self._calculate_backspace_count(target_words)
        print(f"            backspace_count: {backspace_count}")
        self._perform_backspace(backspace_count)

        # Emit pending updates in order
        self._emit_pending_updates()

        # Clear pending updates
        self.pending_updates = {}

    def _emit_pending_updates(self) -> None:
        """Emit only the changed portions of pending updates after common prefix."""
        # Calculate common prefix to determine what to emit after backspace
        original_str = self._build_string_from_words(self.current_words)
        target_words = self.current_words.copy()

        for seq, word in self.pending_updates.items():
            if word:
                target_words[seq] = word
            else:
                if seq in target_words:
                    del target_words[seq]

        target_str = self._build_string_from_words(target_words)
        prefix_len = self._find_common_prefix_length(original_str, target_str)

        print(f"            emission calculation:")
        print(f"              original_str: '{original_str}'")
        print(f"              target_str: '{target_str}'")
        print(f"              prefix_len: {prefix_len}")

        # Build emission string by processing only changed words in order
        emission_parts = []
        pending_seqs = sorted(self.pending_updates.keys())
        chars_processed = prefix_len

        for seq in pending_seqs:
            word = self.pending_updates[seq]
            current_word = self.current_words.get(seq, "")

            # Check if this word actually changed
            if word != current_word:
                # Find this word's position in the target string
                word_start = chars_processed
                word_end = word_start + len(word)

                # Add this word to emission
                emission_parts.append(word)
                print(f"              adding changed word[{seq}]: '{word}'")

                chars_processed = word_end
            else:
                # For unchanged words, just advance the position
                chars_processed += len(word)

        emission_str = ''.join(emission_parts)
        print(f"            final emission_str: '{emission_str}'")

        # Update current_words with all pending changes
        for seq, word in self.pending_updates.items():
            if word:
                self.current_words[seq] = word
            else:
                if seq in self.current_words:
                    del self.current_words[seq]

        # Emit only the changed portion
        if emission_str:
            print(f"            📝 EMIT('{emission_str}')")
            self.keyboard.emit(emission_str)

        # Set last_emitted_seq to highest sequence processed
        if self.pending_updates:
            self.last_emitted_seq = max(self.pending_updates.keys())
    
    def _emit_word_with_gap_fill(self, seq: int, word: str) -> None:
        """Fill gaps between last emitted and current sequence, then emit update."""
        print(f"          _emit_word_with_gap_fill(seq={seq}, word='{word}')")
        print(f"            last_emitted_seq: {self.last_emitted_seq}")

        # Check if this is actually a change
        is_changed = word != self.current_words.get(seq, "")
        print(f"            is_changed: {is_changed}")

        # Fill gaps - emit existing words between last_emitted_seq and seq
        gap_seqs = sorted(k for k in self.current_words.keys()
                         if self.last_emitted_seq < k < seq)
        print(f"            gap_seqs: {gap_seqs}")

        for gap_seq in gap_seqs:
            gap_word = self.current_words[gap_seq]
            print(f"            🔗 GAP FILL EMIT('{gap_word}') for seq={gap_seq}")
            self.keyboard.emit(gap_word)

        # For after-backspace emissions, we need to emit words to maintain sequence
        # even if unchanged, because they need to appear in the correct position
        if word:  # Non-empty update
            print(f"            📝 EMIT('{word}') and UPDATE current_words[{seq}]")
            self.current_words[seq] = word
            self.keyboard.emit(word)
        else:  # Empty update - delete
            if seq in self.current_words:
                print(f"            🗑️  DELETE current_words[{seq}]")
                del self.current_words[seq]
            print(f"            ⚪ NO EMISSION (deletion)")

        print(f"            ➡️  last_emitted_seq = {seq}")
        self.last_emitted_seq = seq
    
    def _build_string_from_words(self, words: Dict[int, str]) -> str:
        """Build complete string from word dictionary."""
        if not words:
            return ""
        return ''.join(words[k] for k in sorted(words.keys()))
    
    def _find_common_prefix_length(self, str1: str, str2: str) -> int:
        """Find length of common prefix between two strings."""
        min_len = min(len(str1), len(str2))
        for i in range(min_len):
            if str1[i] != str2[i]:
                return i
        return min_len