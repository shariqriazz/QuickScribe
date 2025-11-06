"""
Recording Coordinator - Manages recording lifecycle and session state.
"""
import time
from typing import Optional
from recording_session import RecordingSession, RecordingSource
from audio_source import AudioResult
from providers.conversation_context import ConversationContext
from ui import AppState
from lib.pr_log import pr_debug, pr_info


class RecordingCoordinator:
    """Manages recording session lifecycle and audio capture coordination."""

    def __init__(self, audio_source, transcription_service, config, app):
        self.audio_source = audio_source
        self.transcription_service = transcription_service
        self.config = config
        self.app = app
        self._current_session: Optional[RecordingSession] = None

    def start_recording(self, source: RecordingSource) -> bool:
        """Start recording from specified source."""
        if self._current_session:
            pr_debug("Already recording, ignoring")
            return False
        if not self.audio_source:
            pr_debug("No audio source available")
            return False

        self._current_session = RecordingSession(source)
        pr_debug("Calling audio_source.start_recording()")
        self.audio_source.start_recording()
        pr_debug("Recording started")
        self.app._update_tray_state(AppState.RECORDING)
        return True

    def stop_recording(self) -> tuple[RecordingSession, Optional[AudioResult], ConversationContext]:
        """Stop recording and return session, result, and context."""
        if not self._current_session:
            return (None, None, ConversationContext("", "", self.config.sample_rate))

        session = self._current_session
        self._current_session = None
        time.sleep(self.config.mic_release_delay / 1000.0)
        result = self.audio_source.stop_recording()
        context = self._get_conversation_context()
        return (session, result, context)

    def abort_recording(self) -> None:
        """Abort recording without processing."""
        if not self._current_session:
            return

        self._current_session = None
        if self.audio_source:
            self.audio_source.stop_recording()

    def start_signal_recording(self, mode_name: str) -> None:
        """Start recording triggered by signal with mode switch."""
        if self.transcription_service:
            self.transcription_service._handle_mode_change(mode_name)
        pr_info("Starting recording...")
        self.start_recording(RecordingSource.SIGNAL)

    def get_current_session(self) -> Optional[RecordingSession]:
        """Get the current recording session."""
        return self._current_session

    def _get_conversation_context(self) -> ConversationContext:
        """Build conversation context from XMLStreamProcessor state."""
        xml_markup = ""
        compiled_text = ""
        if self.transcription_service:
            xml_markup = self.transcription_service._build_xml_from_processor()
            compiled_text = self.transcription_service._build_current_text()

        return ConversationContext(
            xml_markup=xml_markup,
            compiled_text=compiled_text,
            sample_rate=self.config.sample_rate
        )
