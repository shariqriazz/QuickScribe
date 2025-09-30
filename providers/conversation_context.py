"""
Conversation context data structure for provider interface standardization.
"""
from dataclasses import dataclass


@dataclass
class ConversationContext:
    """
    Context information for transcription requests.
    
    Attributes:
        xml_markup: The XML representation of current conversation state
        compiled_text: The plain text representation of current conversation
        sample_rate: Audio sample rate for format conversions
    """
    xml_markup: str
    compiled_text: str
    sample_rate: int