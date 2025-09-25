"""Keyboard injector interface for XML stream processor."""

from abc import ABC, abstractmethod


class KeyboardInjector(ABC):
    """Abstract interface for keyboard injection operations."""
    
    @abstractmethod
    def bksp(self, count: int) -> None:
        """Backspace count characters."""
        pass
    
    @abstractmethod
    def emit(self, text: str) -> None:
        """Emit text at current cursor position."""
        pass


class MockKeyboardInjector(KeyboardInjector):
    """Mock keyboard injector for testing."""
    
    def __init__(self):
        self.output = ""
        self.operations = []
    
    def bksp(self, count: int) -> None:
        """Backspace by removing characters from end of output."""
        self.operations.append(('bksp', count))
        if count > 0:
            self.output = self.output[:-count]
    
    def emit(self, text: str) -> None:
        """Emit text by appending to output."""
        self.operations.append(('emit', text))
        self.output += text
    
    def reset(self) -> None:
        """Reset mock state."""
        self.output = ""
        self.operations = []