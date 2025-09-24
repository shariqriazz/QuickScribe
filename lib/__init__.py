"""
Library modules for QuickScribe word processing and output management.
"""

from .word_stream import DictationWord, WordStreamParser
from .diff_engine import DiffResult, DiffEngine
from .output_manager import OutputManager, XdotoolError

__all__ = [
    'DictationWord',
    'WordStreamParser',
    'DiffResult', 
    'DiffEngine',
    'OutputManager',
    'XdotoolError'
]