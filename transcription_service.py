"""
Transcription Service - Handles XML processing, streaming, and transcription processing.
"""
import re
from lib.word_stream import WordStreamParser, DictationWord
from lib.diff_engine import DiffEngine
from lib.output_manager import OutputManager, XdotoolError
from lib.conversation_state import ConversationManager


class TranscriptionService:
    """Handles XML transcription processing and streaming."""
    
    def __init__(self, use_xdotool=False):
        self.use_xdotool = use_xdotool
        self.word_parser = WordStreamParser()
        self.diff_engine = DiffEngine()
        self.output_manager = OutputManager() if use_xdotool else None
        self.conversation_manager = ConversationManager()
        
        # State management
        self.current_words = []
        self.streaming_buffer = ""
        self.last_processed_position = 0
        self.conversation_history = []
        self.last_typed_text = ""
        
        # Load conversation state
        self.conversation_manager.load_conversation()
    
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
        self.last_processed_position = 0
    
    def reset_all_state(self):
        """Reset all stored state for a fresh conversation/update baseline."""
        # Clear conversation/history surfaces
        self.conversation_history.clear()
        self.last_typed_text = ""
        # Clear XML processing state
        self.current_words.clear()
        if self.word_parser:
            self.word_parser.clear_buffer()
        # Reset conversation state
        if self.conversation_manager:
            self.conversation_manager.reset_conversation()
        # Reset streaming accumulators
        self.reset_streaming_state()
    
    def process_streaming_chunk(self, chunk_text, output_callback=None):
        """Process streaming text chunks and apply real-time updates."""
        # Add chunk to buffer
        self.streaming_buffer += chunk_text
        
        # Detect and handle <reset> tags in the stream
        reset_pattern = re.compile(r'<reset\s*/>|<reset>.*?</reset>', re.DOTALL | re.IGNORECASE)
        if reset_pattern.search(self.streaming_buffer):
            last_match = None
            for m in reset_pattern.finditer(self.streaming_buffer):
                last_match = m
            self.reset_all_state()
            if last_match:
                self.streaming_buffer = self.streaming_buffer[last_match.end():]
        
        # Look for complete <update> sections with word tags
        update_pattern = re.compile(r'<update>(.*?)</update>', re.DOTALL)
        update_matches = update_pattern.findall(self.streaming_buffer)
        
        if update_matches:
            # Process the most recent complete update section
            latest_update = update_matches[-1]
            
            # Extract word tags from the update
            word_pattern = re.compile(r'<(\d+)>(.*?)</\1>', re.DOTALL)
            word_matches = word_pattern.findall(latest_update)
            
            if word_matches:
                # Create word objects from matches
                new_words = []
                for word_id_str, word_text in word_matches:
                    word_id = int(word_id_str)
                    # Handle empty tags as deletions
                    if word_text.strip() == "":
                        new_words.append(DictationWord(id=word_id, text=None))
                    else:
                        new_words.append(DictationWord(id=word_id, text=word_text))
                
                # Update conversation state incrementally
                if self.conversation_manager:
                    for word in new_words:
                        if word.text is None:
                            self.conversation_manager.state.delete_word(word.id)
                        else:
                            self.conversation_manager.state.update_word(word.id, word.text)
                    
                    # Build updated words list
                    word_items = list(self.conversation_manager.state.words.items())
                    word_items.sort(key=lambda x: x[0])
                    updated_words = [DictationWord(id=word_id, text=text) for word_id, text in word_items]
                    
                    # Calculate and apply diff for real-time updates
                    diff_result = self.diff_engine.compare(self.current_words, updated_words)
                    
                    if self.output_manager and self.use_xdotool:
                        try:
                            self.output_manager.execute_diff(diff_result)
                        except XdotoolError as e:
                            print(f"\nxdotool error: {e}", file=sys.stderr)
                            # Fall back to clipboard for this chunk
                            if diff_result.new_text and output_callback:
                                full_text = self.conversation_manager.state.to_text_from_words(updated_words)
                                output_callback(full_text)
                    else:
                        # Use clipboard method for real-time updates
                        if (diff_result.backspaces > 0 or diff_result.new_text) and output_callback:
                            full_text = self.conversation_manager.state.to_text_from_words(updated_words)
                            output_callback(full_text)
                    
                    # Update current words state
                    self.current_words = updated_words
                    
                    # Show real-time progress
                    compiled_text = self.conversation_manager.state.to_text()
                    print(f"\r[Streaming] {compiled_text}", end='', flush=True)
    
    def process_xml_transcription(self, text, output_callback=None):
        """Process XML transcription text using the word processing pipeline."""
        try:
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
            
            # Parse XML to extract words (including deletions)
            newly_parsed_words = self.word_parser.parse(text_without_conversation)
            if not newly_parsed_words:
                return
            
            # Update conversation state with all parsed words
            if self.conversation_manager:
                for word in newly_parsed_words:
                    if word.text is None:
                        # Handle deletion
                        self.conversation_manager.state.delete_word(word.id)
                    else:
                        # Handle update/addition
                        self.conversation_manager.state.update_word(word.id, word.text)
                
                # Build current words list from conversation state for diff processing
                word_items = list(self.conversation_manager.state.words.items())
                word_items.sort(key=lambda x: x[0])  # Sort by ID
                updated_words = [DictationWord(id=word_id, text=text) for word_id, text in word_items]
            else:
                # Fallback to old behavior if conversation manager not available
                updated_words = self.current_words.copy()
                
                for new_word in newly_parsed_words:
                    if new_word.text is None:
                        # Handle deletion - remove from updated_words
                        updated_words = [w for w in updated_words if w.id != new_word.id]
                    else:
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
            
            # Calculate diff and execute changes
            diff_result = self.diff_engine.compare(self.current_words, updated_words)
            
            if self.output_manager and self.use_xdotool:
                # Use the sophisticated output manager for xdotool
                try:
                    self.output_manager.execute_diff(diff_result)
                except XdotoolError as e:
                    print(f"\nxdotool error: {e}", file=sys.stderr)
                    print("Falling back to clipboard method...", file=sys.stderr)
                    # Fall back to clipboard method
                    if diff_result.new_text and output_callback:
                        full_text = self.conversation_manager.state.to_text_from_words(updated_words)
                        output_callback(full_text)
            else:
                # Use callback method - but we still need to handle the diff properly
                if (diff_result.backspaces > 0 or diff_result.new_text) and output_callback:
                    # For callback method, output the full corrected text
                    full_text = self.conversation_manager.state.to_text_from_words(updated_words)
                    output_callback(full_text)
            
            # Update current words state
            self.current_words = updated_words
        
        except Exception as e:
            print(f"\nError processing XML transcription: {e}", file=sys.stderr)