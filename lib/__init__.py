"""
Library modules for QuickScribe word processing and output management.
"""

from .keyboard_injector_xdotool import XdotoolKeyboardInjector
from .keyboard_injector_macos import MacOSKeyboardInjector
from .keyboard_injector_windows import WindowsKeyboardInjector

__all__ = [
    'XdotoolKeyboardInjector',
    'MacOSKeyboardInjector',
    'WindowsKeyboardInjector',
]