"""
Recording session identity representing who initiated a recording.
"""
import time
from enum import Enum


class RecordingSource(Enum):
    """Source that initiated the recording."""
    KEYBOARD = "keyboard"
    SIGNAL = "signal"
    SYSTEM_TRAY = "system_tray"


class RecordingSession:
    """Session identity representing who initiated a recording."""

    def __init__(self, source: RecordingSource):
        self.source: RecordingSource = source
        self.start_time: float = time.time()

    def should_abort_on_keystroke(self) -> bool:
        """Check if keystroke should abort this recording."""
        return self.source == RecordingSource.KEYBOARD
