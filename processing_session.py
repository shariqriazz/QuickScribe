"""
Processing infrastructure for a recording session.
"""
import queue
import threading
from recording_session import RecordingSession
from providers.conversation_context import ConversationContext
from audio_source import AudioResult


class ProcessingSession:
    """Processing infrastructure for a recording session."""

    def __init__(
        self,
        recording_session: RecordingSession,
        context: ConversationContext,
        audio_result: AudioResult
    ):
        self.recording_session: RecordingSession = recording_session
        self.context: ConversationContext = context
        self.audio_result: AudioResult = audio_result
        self.chunk_queue: queue.Queue = queue.Queue()
        self.chunks_complete: threading.Event = threading.Event()
