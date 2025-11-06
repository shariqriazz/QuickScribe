"""
Processing Coordinator - Orchestrates the two-queue processing pipeline.
"""
import threading
from typing import Optional
from recording_session import RecordingSession
from processing_session import ProcessingSession
from audio_source import AudioResult, AudioDataResult
from providers.conversation_context import ConversationContext
from lib.event_queue import EventQueue
from ui import AppState


class ProcessingCoordinator:
    """Orchestrates parallel model invocation and sequential output processing."""

    def __init__(self, provider, transcription_service, config, app):
        self.provider = provider
        self.transcription_service = transcription_service
        self.config = config
        self.app = app
        self.session_queue = None

    def initialize(self):
        """Initialize the session processing queue."""
        from session_output_worker import process_session_output

        self.session_queue = EventQueue(
            lambda s: process_session_output(self.transcription_service, self.config, s),
            name="SessionProcessor"
        )
        self.session_queue.start()
        return True

    def process_recording_result(
        self,
        session: RecordingSession,
        result: Optional[AudioResult],
        context: ConversationContext
    ):
        """Process recording result and orchestrate session handling."""
        if not result:
            self.app._return_to_idle()
            return

        if isinstance(result, AudioDataResult) and len(result.audio_data) == 0:
            self.app._return_to_idle()
            return

        self.app._update_tray_state(AppState.PROCESSING)
        processing_session = ProcessingSession(session, context, result)
        self.session_queue.enqueue(processing_session)

        from model_invocation_worker import invoke_model_for_session
        threading.Thread(
            target=invoke_model_for_session,
            args=(self.provider, processing_session, result),
            daemon=True
        ).start()

        self.app._show_recording_prompt()

    def shutdown(self):
        """Shutdown the session queue."""
        if self.session_queue:
            self.session_queue.shutdown()
