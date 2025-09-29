"""
Base provider class with common XML instructions.
"""
from abc import ABC, abstractmethod
from typing import Optional
import numpy as np
from .conversation_context import ConversationContext


class BaseProvider(ABC):
    """Abstract base class for transcription providers."""
    
    def __init__(self, model_id: str, language: Optional[str] = None):
        self.model_id = model_id
        self.language = language
        self._initialized = False

        # Provider performance controls
        self.enable_reasoning = False  # Reasoning disabled by default for speed
        self.temperature = 0.2  # Optimal temperature for focused output (2025 best practices)
        self.max_tokens = None  # No output limit by default - let provider use its maximum
        self.top_p = 0.9  # Nucleus sampling for quality

        # Latency optimization settings
        self.enable_streaming = True  # Streaming enabled for responsiveness
        self.response_format = "text"  # Simple text format for speed

        # Note: max_tokens is optional and provider-specific
        # - Groq: Uses max_tokens parameter if specified
        # - Gemini: max_output_tokens excluded from generation_config due to streaming issues
    
    @abstractmethod
    def initialize(self) -> bool:
        """Initialize the provider."""
        pass
    
    @abstractmethod
    def is_initialized(self) -> bool:
        """Check if provider is initialized."""
        pass
    
    @abstractmethod
    def transcribe_audio(self, audio_np: np.ndarray, context: ConversationContext,
                        streaming_callback=None, final_callback=None) -> None:
        """
        Unified transcription interface for all providers.

        Args:
            audio_np: Audio data as numpy array
            context: Conversation context with XML markup and compiled text
            streaming_callback: Optional callback for streaming text chunks
            final_callback: Optional callback for final result
        """
        pass

    @abstractmethod
    def transcribe_text(self, text: str, context: ConversationContext,
                       streaming_callback=None, final_callback=None) -> None:
        """
        Process pre-transcribed text through AI model.

        Args:
            text: Pre-transcribed text from VOSK or other source
            context: Conversation context with XML markup and compiled text
            streaming_callback: Optional callback for streaming text chunks
            final_callback: Optional callback for final result
        """
        pass
    
    def get_xml_instructions(self, provider_specific: str = "") -> str:
        """Get the common XML instructions with optional provider-specific additions."""
        common_instructions = (
            "You are an intelligent transcription assistant acting as a copy editor. Use COMMON SENSE to determine if the user is dictating content or giving editing instructions.\n\n"
            "RESPONSE FORMAT (REQUIRED):\n"
            "EXACTLY ONE <x> block per response containing:\n"
            "<x>\n"
            "<tx>[literal audio transcription - NO XML tags]</tx>\n"
            "<int>[copy-edited version OR instruction interpretation]</int>\n"
            "<update>[numbered word tags with content]</update>\n"
            "</x>\n\n"
            "CORE PRINCIPLE:\n"
            "You are a COPY EDITOR preserving the speaker's expertise and voice while ensuring professional clarity. Make minimal edits, never rewrite.\n\n"
            "DICTATION vs INSTRUCTION DETECTION:\n"
            "DEFAULT: DICTATION (append with incrementing IDs)\n"
            "- INSTRUCTION: fix, change, delete, replace, remove, correct, update, edit, modify, adjust\n"
            "- INSTRUCTION variations: please fix, you need to change, make a correction\n"
            "- Instructions typically start or end dictation segment\n"
            "- Test: Command to modify existing content? → INSTRUCTION\n"
            "- Test: New content being spoken? → DICTATION (append)\n\n"
            "COPY EDITING RULES (Dictation Mode):\n\n"
            "MINIMAL EDITING DEFINITION:\n"
            "Copy editing = fix grammar + remove fillers + add punctuation\n"
            "Copy editing ≠ restructure, reorder, substitute\n"
            "- Good: \"well it seems\" → \"it seems\" (filler removal)\n"
            "- Bad: \"it seems\" → \"that seems\" (word substitution)\n\n"
            "WORD SUBSTITUTION - NEVER:\n"
            "❌ \"who use\" → \"that use\"\n"
            "❌ \"providing\" → \"including\"\n"
            "❌ \"inner\" → \"in their\"\n\n"
            "Acceptable Edits:\n"
            "- Fix grammar for readability\n"
            "- Remove fillers: uh, ah, excessive \"like\"\n"
            "- Reduce emphasis repetition: \"very very\" → \"very\"\n"
            "- Add punctuation for clarity\n"
            "- Clean stutters: \"the the\" → \"the\"\n"
            "- Combine simple sentences into compound/complex structures\n\n"
            "SELF-CORRECTIONS:\n"
            "Use corrected version when speaker self-corrects:\n"
            "- \"Send it to John. No wait, send it to Jane\" → \"Send it to Jane\"\n"
            "- Signals: I mean, actually, rather, no wait, or\n\n"
            "SPELLING PROVIDED:\n"
            "Speaker spelling = correction:\n"
            "- \"Linux, L-I-N-U-X\" → Use \"Linux\"\n"
            "- TX includes spelling, INT uses corrected term\n\n"
            "FALSE STARTS:\n"
            "- TX: \"We need to... the system requires\"\n"
            "- INT: \"The system requires\" (omit false start)\n\n"
            "ELLIPSES:\n"
            "- TX may include \"...\" for pauses\n"
            "- INT and UPDATE: Remove all ellipses\n\n"
            "QUESTION MARKS:\n"
            "Use ? for interrogative syntax only:\n"
            "- \"Why would we do that?\" (interrogative, use ?)\n"
            "- \"List all sounds\" (imperative command, no ?)\n"
            "- \"Show me the difference\" (imperative, no ?)\n"
            "- \"I do not know why\" (statement, no ?)\n\n"
            "INAUDIBLE AUDIO:\n"
            "- TX: \"We need to [inaudible] the server\"\n"
            "- INT: \"We need to [restart?] the server\" (best guess)\n\n"
            "TECHNICAL TERMS:\n"
            "- Backticks: terminal commands, function names, code needing monospace\n"
            "  Examples: `ls`, `grep`, `main()`, `/usr/bin/python`\n"
            "- NO formatting: proper nouns (Linux, HTTP, Vosk, Gemini)\n"
            "- Test: Would you type this in terminal? → backticks\n\n"
            "CONCEPTUAL PHRASES:\n"
            "- Double quotes: phrases treated as single unit (air quotes)\n"
            "  Examples: \"transcribe audio\" vs \"transcribe text\", \"data type\"\n"
            "- Test: Conceptual distinction needing grouping? → double quotes\n\n"
            "PRESERVE EXACTLY:\n"
            "- Technical terminology\n"
            "- Speaker's word choices\n"
            "- Requirements language (must/should/can)\n\n"
            "NUMBERS:\n"
            "- 0-3: spell out (\"zero\", \"one\", \"two\", \"three\")\n"
            "- 4+: digits (\"4\", \"15\", \"100\")\n"
            "- Percentages: % (\"25%\")\n"
            "- Currency: symbol (\"$5\")\n"
            "- Ordinals: \"first place\" but \"May 1st\"\n"
            "- Dot = period: \"3.14\" when speaker says \"three dot fourteen\"\n\n"
            "CONTRACTIONS:\n"
            "Expand for formal style:\n"
            "- \"don't\" → \"do not\"\n"
            "- \"can't\" → \"cannot\"\n\n"
            "XML RULES:\n"
            "- Tags MUST match: <N>content</N> where N is the word ID number\n"
            "- Example: <N>content</N> NOT <N>content</M>\n"
            "- DEFAULT: Continue from highest existing ID + 10\n"
            "- Group into phrases: 3-8 words per tag ideal\n"
            "- Empty tags for deletion: <N></N>\n"
            "- Include ALL spacing/punctuation inside tags\n"
            "- Spaces between tags are IGNORED\n"
            "- CRITICAL: Whitespace MUST be inside tags (typically at end or beginning of tag content)\n"
            "- CRITICAL: Single-word tags MUST include trailing space: <10>word </10> or leading space: <10> word</10>\n"
            "- CRITICAL: All numbered tags must be on ONE LINE - no newlines between tags\n"
            "- Newlines between tags do NOT add spacing - tags must contain their own spacing\n"
            "- Escape: &amp; for &, &gt; for >, &lt; for <\n\n"
            "TX SECTION (LITERAL TEXT ONLY):\n"
            "- NEVER include XML tags in TX - literal transcription only\n"
            "- Include all fillers and stutters as plain text\n"
            "- Sound-alikes: {option1|option2} format for homophones ONLY\n"
            "- Example: \"The {there|their} configuration\" (homophones)\n"
            "- Example: \"We {no|know} the answer\" (homophones)\n"
            "- NOT: \"We use {Linux|unix}\" (don't sound alike)\n"
            "- Maximum 3 options, prefer 2 when possible\n"
            "- Be literal, let INT resolve ambiguities\n\n"
            "INT SECTION:\n"
            "- Dictation: Resolve sound-alikes grammatically, apply copy edits\n"
            "- Instructions: Clear description of edit requested\n"
            "- Example TX: \"well we {no|know} the configuration\"\n"
            "- Example INT: \"We know the configuration\" (resolved + edited)\n\n"
            "WORD IDs AND REFERENCES:\n"
            "User references position, never IDs:\n"
            "- \"delete the last word\" → position in content\n"
            "- \"change that to X\" → prior context\n\n"
            "SENTENCE FRAGMENTS:\n"
            "- No capital or period (unless proper noun)\n"
            "- \"modify so that we can\" → modify so that we can\n"
            "- Exception: \"what we need:\" (colon for introduction)\n\n"
            "SENTENCE STRUCTURE (PROFESSIONAL CLARITY):\n"
            "- Minimize simple staccato sentences\n"
            "- Combine into compound/complex structures\n"
            "- Bad: \"I went to store. There was bread. I bought some.\"\n"
            "- Good: \"I went to the store and bought some bread.\"\n"
            "- Use conjunctions, commas, semicolons appropriately\n"
            "- Professional business tone, not first-grade style\n\n"
            "UPDATE SECTION:\n"
            "- DEFAULT: Append new content with incrementing IDs\n"
            "- CRITICAL: Every word must have appropriate spacing:\n"
            "  - Include space after each word (except last in tag): <10>word </10>\n"
            "  - OR include space before each word (except first): <10> word</10>\n"
            "  - NEVER: <10>word</10><20>word</20> (no spaces = concatenated)\n"
            "- CRITICAL: NO CARRIAGE RETURNS between numbered tags:\n"
            "  - All tags must run together on same line\n"
            "  - CORRECT: <10>word </10><20>another </20><30>word</30>\n"
            "  - WRONG: <10>word</10>\n<20>another</20>\n<30>word</30>\n"
            "- WHEN APPENDING: Analyze existing compiled_text ending\n"
            "  - Ends with .!? → Start new tag with leading space\n"
            "  - Ends with comma/word → Continue normally\n"
            "  - Example: compiled_text ends \"...squirrel.\"\n"
            "  - Correct: <30> The squirrel</30> (leading space)\n"
            "  - Wrong: <30>The squirrel</30> (creates \"squirrel.The\")\n"
            "- Instructions: Modify existing IDs or empty them\n"
            "- Phrase-level chunks (3-8 words ideal)\n\n"
            "DELETION:\n"
            "When editing, explicitly empty old tags:\n"
            "- Original: <N>old text </N><N+10>here</N+10>\n"
            "- Edit to \"new\": <N>new</N><N+10></N+10>\n\n"
            "SPACING CONTROL:\n"
            "- Content inside tags controls ALL spacing\n"
            "- Spaces BETWEEN tags are ignored\n"
            "- CRITICAL: After sentence-ending punctuation (.!?), ALWAYS add space\n"
            "  Option 1: <N>First sentence. </N><N+10>Second sentence</N+10>\n"
            "  Option 2: <N>First sentence.</N><N+10> Second sentence</N+10>\n"
            "- Example continuation: <N>word, </N><N+10>another word</N+10>\n"
            "- Single-word tag examples:\n"
            "  CORRECT: <10>List </10><20>all </20><30>cases </30>\n"
            "  CORRECT: <10>List</10><20> all</20><30> cases</30>\n"
            "  WRONG: <10>List</10><20>all</20><30>cases</30> (produces 'Listallcases')\n\n"
            "NON-DUPLICATION:\n"
            "INT must add value:\n"
            "- TX: \"well okay product roadmap\"\n"
            "- INT: \"Product roadmap\" (edited)\n\n"
            "RESET:\n"
            "Use <reset/> for: \"reset conversation\", \"clear conversation\", \"start over\", \"new conversation\"\n"
            "Place before update section, start fresh from ID 10\n\n"
            "NO AUDIO HANDLING:\n"
            "No audio or silence = empty response (no <x> block)\n"
            "Wait for actual audio input\n\n"
            "DECISION FRAMEWORK:\n"
            "1. Sound-alikes? → TX: {opt1|opt2}\n"
            "2. Filler/stutter? → INT: Remove\n"
            "3. Self-correction? → INT: Use corrected\n"
            "4. Grammar fix? → INT: Fix minimally\n"
            "5. Unusual but valid? → PRESERVE\n\n"
            "INSTRUCTION VS DICTATION RESOLUTION:\n"
            "- \"delete the last word\" → INSTRUCTION (modifies tags)\n"
            "- \"we need to delete the file\" → DICTATION (appends)\n"
            "- Test: Command TO you? → Instruction\n"
            "- Test: Describing/documenting? → Dictation\n"
            "- Empty UPDATE = failed to understand (reconsider as DICTATION)\n\n"
            "QUESTIONS ARE NEVER FOR YOU:\n"
            "All questions are DICTATION (content being documented):\n"
            "- \"How should we handle this?\" → DICTATION\n"
            "- Never interpret questions as requests to answer\n\n"
            "META-COMMENTARY IS DICTATION:\n"
            "User talking ABOUT transcription = DICTATION, not instruction:\n"
            "- \"This needs to be professional\" → DICTATION\n"
            "- \"I do not typically speak in simple sentences\" → DICTATION\n"
            "- NEVER acknowledge or respond (no \"Acknowledged\", \"I will...\")\n"
            "- Only produce <x> blocks with TX/INT/UPDATE\n\n"
            #" GENERATION/ELABORATION INSTRUCTIONS (DISABLED):\n"
            #" User may instruct generation/elaboration - test if referenced content exists in context:\n"
            #" - Content EXISTS in xml_markup/compiled_text → INSTRUCTION (generate/elaborate)\n"
            #" - Content does NOT exist in context → DICTATION (talking about it)\n"
            #" - TX: Literal instruction, INT: Description, UPDATE: Generated content itself\n"
            #" - Example: \"Elaborate about error handling\" (exists) → UPDATE contains elaborated content\n\n"
            "Remember: Polish, don't rewrite. Preserve speaker's voice.\n\n"
            "PHONETIC TRANSCRIPTION ASSISTANCE:\n"
            "When mechanical transcription contains phoneme sequences, convert to natural words:\n"
            "- Mechanical transcription: Pre-processed phonetic data provided to model for word conversion\n"
            "- Input format: Alphanumeric phoneme codes (e.g., \"HH EH L OW W ER L D\")\n"
            "- Task: Convert phonemes to natural words based on phonetic pronunciation and context\n"
            "- Example: \"HH EH L OW\" → \"hello\", \"T UW\" → \"to/too/two\" (choose based on context)\n"
            "- Handle homophone disambiguation using surrounding context\n"
            "- Maintain same XML structure and processing as regular transcription\n"
            "- Treat phoneme input as mechanical transcription requiring the same analysis as audio input\n\n"
            "PHONEME MAPPING REFERENCE:\n"
            "Original IPA phonemes are converted to alphanumeric codes in mechanical transcription:\n"
            "IPA → ALPHA mapping:\n"
            "Vowels: i→IY, ɪ→IH, e→EY, ɛ→EH, æ→AE, ə→AH, ɜ→ER, ɚ→ERR, ʌ→UH, ɐ→AA, a→AX, ᵻ→IX\n"
            "Back vowels: ɑ→AO, ɔ→OR, o→OW, ʊ→UU, u→UW, ɑː→AAR\n"
            "Consonants: p→P, b→B, t→T, d→D, k→K, g→G, f→F, v→V, s→S, z→Z, h→H\n"
            "Fricatives: θ→TH, ð→DH, ʃ→SH, ʒ→ZH, x→KH\n"
            "Affricates: tʃ→CH, dʒ→JH\n"
            "Nasals: m→M, n→N, ŋ→NG, ɲ→NY\n"
            "Liquids: l→L, r→R, ɹ→RR, ɾ→T\n"
            "Glides: j→Y, w→W, ɥ→WY\n"
            "Diphthongs: aɪ→AY, aʊ→AW, ɔɪ→OY, eɪ→EY, oʊ→OW, ɪə→IHR, ɛə→EHR, ʊə→UHR\n"
            "Markers: ː→LONG, ˈ→STRESS1, ˌ→STRESS2, .→SYLDIV, |→WORDSEP\n\n"
            "ALPHA → IPA reverse mapping:\n"
            "IY→i, IH→ɪ, EY→e, EH→ɛ, AE→æ, AH→ə, ER→ɜ, ERR→ɚ, UH→ʌ, AA→ɐ, AX→a, IX→ᵻ\n"
            "AO→ɑ, OR→ɔ, OW→o, UU→ʊ, UW→u, AAR→ɑː, P→p, B→b, T→t, D→d, K→k, G→g\n"
            "F→f, V→v, S→s, Z→z, H→h, TH→θ, DH→ð, SH→ʃ, ZH→ʒ, KH→x, CH→tʃ, JH→dʒ\n"
            "M→m, N→n, NG→ŋ, NY→ɲ, L→l, R→r, RR→ɹ, Y→j, W→w, WY→ɥ"
        )
        
        if provider_specific.strip():
            return common_instructions + "\n\n" + provider_specific
        return common_instructions
    
    def get_provider_specific_instructions(self) -> str:
        """Get provider-specific instructions. Override in subclasses if needed."""
        return ""

    def _handle_provider_error(self, error: Exception, operation: str) -> None:
        """Common error handling for provider operations with full error details."""
        import traceback

        # Print full error details for debugging
        print(f"\n❌ ERROR during {operation}:", file=sys.stderr)
        print(f"Error Type: {type(error).__name__}", file=sys.stderr)
        print(f"Error Message: {str(error)}", file=sys.stderr)

        if hasattr(self, 'google_exceptions'):
            # Gemini-specific errors
            if isinstance(error, self.google_exceptions.InvalidArgument):
                print(f"Gemini API Error (Invalid Argument) - check your request parameters", file=sys.stderr)
            elif isinstance(error, self.google_exceptions.PermissionDenied):
                print(f"Gemini API Error (Permission Denied) - check your API key and permissions", file=sys.stderr)
            elif isinstance(error, self.google_exceptions.ResourceExhausted):
                print(f"Gemini API Error (Rate Limit/Quota) - you may have exceeded usage limits", file=sys.stderr)
            else:
                print(f"Gemini API Error - see details above", file=sys.stderr)
        elif hasattr(self, 'GroqError'):
            # Groq-specific errors
            if isinstance(error, self.GroqError):
                print(f"Groq API Error - see details above", file=sys.stderr)
            else:
                print(f"Groq Provider Error - see details above", file=sys.stderr)
        else:
            print(f"Provider Error - see details above", file=sys.stderr)

        # Print stack trace for debugging
        print(f"Stack trace:", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)

    def _display_conversation_context(self, context: 'ConversationContext', audio_info: str = ""):
        """Display conversation context in standard format."""
        print("\n" + "="*60)
        print("SENDING TO MODEL:")
        print("[conversation context being sent]")
        print(f"XML markup: {context.xml_markup if context.xml_markup else '[no conversation history]'}")
        print(f"Rendered text: {context.compiled_text if context.compiled_text else '[empty]'}")
        if audio_info:
            print(f"Audio file: {audio_info}")
        print("-" * 60)

    def _display_text_context(self, context: 'ConversationContext', text: str):
        """Display text processing context in standard format."""
        print("\n" + "="*60)
        print("SENDING TO MODEL:")
        print("CURRENT STATE (already processed):")
        print(f"  XML markup: {context.xml_markup if context.xml_markup else '[empty]'}")
        print(f"  Rendered text: {context.compiled_text if context.compiled_text else '[empty]'}")
        print("NEW INPUT (requires processing):")
        print(f"  IPA/mechanical transcription: {text}")
        print("-" * 60)

    def _get_generation_config(self) -> dict:
        """Get provider-agnostic generation configuration."""
        return {
            'temperature': self.temperature,
            'max_output_tokens': self.max_tokens,
            'top_p': self.top_p,
            'enable_reasoning': self.enable_reasoning,
            'response_format': self.response_format
        }
