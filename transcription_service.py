"""
Transcription Service - Handles XML processing, streaming, and transcription processing.
"""
import re
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'lib', 'xml-stream'))
from xml_stream_processor import XMLStreamProcessor
from keyboard_injector import MockKeyboardInjector
from lib.keyboard_injector_xdotool import XdotoolKeyboardInjector
from lib.keyboard_injector_macos import MacOSKeyboardInjector
from lib.keyboard_injector_windows import WindowsKeyboardInjector
from instruction_composer import InstructionComposer


class TranscriptionService:
    """Handles XML transcription processing and streaming."""

    def __init__(self, config):
        self.config = config
        self.composer = InstructionComposer()

        # Select keyboard injector based on platform
        try:
            if sys.platform == 'darwin':
                self.keyboard = MacOSKeyboardInjector(config)
            elif sys.platform.startswith('linux') or sys.platform.startswith('freebsd'):
                self.keyboard = XdotoolKeyboardInjector(config)
            elif sys.platform == 'win32':
                self.keyboard = WindowsKeyboardInjector(config)
            else:
                print(f"Warning: No supported keyboard injector for platform '{sys.platform}'. Using mock mode (no keyboard output).", file=sys.stderr)
                self.keyboard = MockKeyboardInjector()
        except ImportError as e:
            print(f"Warning: Could not initialize keyboard injector: {e}. Using mock mode (no keyboard output).", file=sys.stderr)
            self.keyboard = MockKeyboardInjector()

        self.processor = XMLStreamProcessor(self.keyboard, debug_enabled=getattr(config, 'debug_enabled', False))
        
        # State management
        self.streaming_buffer = ""
        self.last_update_position = 0
        self.update_seen = False
    
    def detect_and_execute_commands(self, text):
        """Detect commands in transcribed text and execute them. Returns the text with commands removed."""
        # Command patterns to detect
        reset_patterns = [
            "reset conversation",
            "clear conversation", 
            "start over",
            "new conversation",
            "clear context"
        ]
        
        text_lower = text.lower().strip()
        
        # Check for reset commands
        for pattern in reset_patterns:
            if pattern in text_lower:
                print(f"\nCommand detected: '{pattern}' - Resetting conversation...")
                self.reset_all_state()
                text = re.sub(re.escape(pattern), '', text, flags=re.IGNORECASE).strip()
                break
        
        return text
    
    def reset_streaming_state(self):
        """Reset streaming state for new transcription."""
        self.streaming_buffer = ""
        self.last_update_position = 0
        self.update_seen = False
        # Reset processor state if --once flag is enabled
        if getattr(self.config, 'reset_state_each_response', False):
            self.processor.reset({})
    
    def reset_all_state(self):
        """Reset all stored state for a fresh conversation/update baseline."""
        # Reset XML processing state
        self.processor.reset({})
        # Reset streaming accumulators
        self.reset_streaming_state()

    def complete_stream(self):
        """Complete streaming by processing any remaining content and calling end_stream."""
        try:
            # Process any remaining complete tags in the streaming buffer (if any)
            if self.streaming_buffer:
                import re
                matches = re.finditer(r'<(\d+)>(.*?)</\1>', self.streaming_buffer, re.DOTALL)
                remaining_tags = []

                for match in matches:
                    seq_num = int(match.group(1))
                    word_content = match.group(2)
                    # Only process if not already in processor
                    if seq_num not in self.processor.current_words:
                        remaining_tags.append(f'<{seq_num}>{word_content}</{seq_num}>')

                # Process any remaining complete tags
                if remaining_tags:
                    remaining_xml = ''.join(remaining_tags)
                    if self.config.debug_enabled:
                        print(f"[DEBUG] complete_stream: processing remaining tags: {remaining_xml}", file=sys.stderr)
                    self.processor.process_chunk(remaining_xml)

            # Always call end_stream if there are words that haven't been emitted yet
            # This ensures all words get flushed regardless of streaming state
            if self.processor.current_words:
                max_seq = max(self.processor.current_words.keys())
                if self.processor.last_emitted_seq < max_seq:
                    if self.config.debug_enabled:
                        print(f"[DEBUG] complete_stream: calling end_stream to flush remaining words (last_emitted: {self.processor.last_emitted_seq}, max_seq: {max_seq})", file=sys.stderr)
                    self.processor.end_stream()

            if self.config.debug_enabled:
                print(f"[DEBUG] complete_stream: stream completed", file=sys.stderr)

        except Exception as e:
            print(f"Error in complete_stream: {e}", file=sys.stderr)
    
    def _handle_mode_change(self, new_mode: str):
        """Reset state for new mode."""
        if not self.composer:
            print(f"Warning: Cannot change mode - composer not available", file=sys.stderr)
            return False

        available_modes = self.composer.get_available_modes()
        if new_mode not in available_modes:
            print(f"Warning: Invalid mode '{new_mode}' - available: {available_modes}", file=sys.stderr)
            return False

        # Reset state
        self.reset_all_state()

        # Update configuration (single source of truth)
        self.config.mode = new_mode

        print(f"\n[Mode switched to: {new_mode}]", file=sys.stderr)
        return True

    def process_streaming_chunk(self, chunk_text):
        """Process streaming text chunks and apply real-time updates."""
        try:
            # Detect mode changes in the stream
            if '<mode>' in self.streaming_buffer or '<mode>' in chunk_text:
                combined = self.streaming_buffer + chunk_text
                mode_match = re.search(r'<mode>(\w+)</mode>', combined)
                if mode_match:
                    new_mode = mode_match.group(1)
                    if self._handle_mode_change(new_mode):
                        # Clear buffer and skip content processing
                        self.streaming_buffer = ""
                        self.last_update_position = 0
                        self.update_seen = False
                        return

            # Start streaming mode on first chunk with <update>
            if not self.processor.streaming_active and '<update>' in chunk_text:
                self.processor.start_stream()

            # Add chunk to buffer
            self.streaming_buffer += chunk_text

            # Detect and handle <reset> tags in the stream
            if '<reset' in self.streaming_buffer:
                # Find last reset tag
                last_reset_idx = self.streaming_buffer.rfind('<reset')
                if last_reset_idx != -1:
                    # Look for end of reset tag
                    reset_end = self.streaming_buffer.find('>', last_reset_idx)
                    if reset_end != -1:
                        self.reset_all_state()
                        # Keep content after reset tag
                        self.streaming_buffer = self.streaming_buffer[reset_end + 1:]
                        self.last_update_position = 0
                        self.update_seen = False

            # Handle incremental streaming after <update> tag
            if '<update>' in self.streaming_buffer:
                if not self.update_seen:
                    # First time seeing update tag
                    self.update_seen = True
                    update_idx = self.streaming_buffer.find('<update>')
                    self.last_update_position = update_idx + 8  # len('<update>')

                # Stream new content only (content after last processed position)
                if self.last_update_position < len(self.streaming_buffer):
                    new_content = self.streaming_buffer[self.last_update_position:]
                    if new_content:
                        self.processor.process_chunk(new_content)
                        self.last_update_position = len(self.streaming_buffer)

        except Exception as e:
            print(f"\n❌ STREAMING ERROR: {type(e).__name__}: {e}", file=sys.stderr)
            print(f"Last processed position: {self.last_update_position}", file=sys.stderr)
            print(f"Buffer length: {len(self.streaming_buffer)}", file=sys.stderr)
            print(f"Buffer content: {repr(self.streaming_buffer[-100:])}", file=sys.stderr)
            # Always flush debug on error
            self.processor._flush_debug_buffer()
            raise
    
    def process_xml_transcription(self, text):
        """Process XML transcription text using the word processing pipeline."""
        try:
            # Detect and handle mode changes
            mode_match = re.search(r'<mode>(\w+)</mode>', text)
            if mode_match:
                new_mode = mode_match.group(1)
                if self._handle_mode_change(new_mode):
                    return  # Skip content processing for mode changes

            # Check for conversation tags first
            conversation_pattern = re.compile(r'<conversation>(.*?)</conversation>', re.DOTALL)
            conversation_matches = conversation_pattern.findall(text)

            # Detect and handle <reset> tags before processing words
            reset_pattern = re.compile(r'<reset\s*/>|<reset>.*?</reset>', re.DOTALL | re.IGNORECASE)
            if reset_pattern.search(text):
                self.reset_all_state()
                text = reset_pattern.sub('', text)
            
            # Process conversation content
            for conversation_content in conversation_matches:
                content = conversation_content.strip()
                if content:
                    # Process commands in conversation content
                    cleaned_content = self.detect_and_execute_commands(content)
                    if cleaned_content.strip():
                        print(f"AI: {cleaned_content}")
            
            # Remove conversation tags from text before processing words
            text_without_conversation = conversation_pattern.sub('', text)
            
            # Use XMLStreamProcessor for final processing
            self.processor.process_chunk(text_without_conversation)
            self.processor.end_stream()
        
        except Exception as e:
            print(f"\nError processing XML transcription: {e}", file=sys.stderr)
    
    def _build_current_text(self):
        """Build current text from XMLStreamProcessor state."""
        return self.processor._build_string_from_words(self.processor.current_words)
    
    def _build_xml_from_processor(self):
        """Build XML markup from XMLStreamProcessor state."""
        if not self.processor.current_words:
            return ""
        
        # Build XML with proper escaping
        xml_parts = []
        for word_id in sorted(self.processor.current_words.keys()):
            text = self.processor.current_words[word_id]
            # Basic XML escaping
            escaped_text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            xml_parts.append(f'<{word_id}>{escaped_text}</{word_id}>')
        
        return ''.join(xml_parts)