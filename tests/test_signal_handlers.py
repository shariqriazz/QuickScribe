"""Tests for signal handler functionality."""
import pytest
import signal
import sys
from unittest.mock import Mock, patch, MagicMock

sys.modules['pynput'] = Mock()
sys.modules['pynput.keyboard'] = Mock()

mock_qt = MagicMock()
sys.modules['PyQt6'] = mock_qt
sys.modules['PyQt6.QtWidgets'] = mock_qt.QtWidgets
sys.modules['PyQt6.QtCore'] = mock_qt.QtCore
sys.modules['PyQt6.QtGui'] = mock_qt.QtGui

from dictation_app import DictationApp
from config_manager import ConfigManager


class TestSignalHandlers:
    """Test signal handler behavior."""

    def setup_method(self):
        """Setup test fixtures."""
        from recording_coordinator import RecordingCoordinator
        from processing_coordinator import ProcessingCoordinator
        from input_coordinator import InputCoordinator

        self.config = ConfigManager()
        self.config.sigusr1_mode = "dictate"
        self.config.sigusr2_mode = "shell"
        self.config.mic_release_delay = 0
        self.config.sample_rate = 16000
        self.config.trigger_key_name = None

        self.app = DictationApp()
        self.app.config = self.config
        self.app.transcription_service = Mock()
        self.app.audio_source = Mock()
        self.app.provider = Mock()

        self.app.recording_coordinator = RecordingCoordinator(
            self.app.audio_source,
            self.app.transcription_service,
            self.config,
            self.app
        )

        self.app.processing_coordinator = ProcessingCoordinator(
            self.app.provider,
            self.app.transcription_service,
            self.config,
            self.app
        )

        self.app.processing_coordinator.initialize()

        self.app.input_coordinator = InputCoordinator(self.config, self.app)

        self.app._update_tray_state = Mock()
        self.app._show_recording_prompt = Mock()

    def test_sigusr1_switches_mode_and_starts_recording(self):
        """Verify SIGUSR1 switches to sigusr1_mode and starts recording."""
        self.app.input_coordinator._handle_signal_channel("mode_switch_1")

        self.app.transcription_service._handle_mode_change.assert_called_once_with("dictate")
        assert self.app.recording_coordinator._current_session is not None
        self.app.audio_source.start_recording.assert_called_once()

    def test_sigusr2_switches_mode_and_starts_recording(self):
        """Verify SIGUSR2 switches to sigusr2_mode and starts recording."""
        self.app.input_coordinator._handle_signal_channel("mode_switch_2")

        self.app.transcription_service._handle_mode_change.assert_called_once_with("shell")
        assert self.app.recording_coordinator._current_session is not None
        self.app.audio_source.start_recording.assert_called_once()

    def test_sighup_stops_recording(self):
        """Verify SIGHUP stops recording."""
        from recording_session import RecordingSession, RecordingSource
        from audio_source import AudioDataResult
        from providers.conversation_context import ConversationContext

        self.app.recording_coordinator._current_session = RecordingSession(RecordingSource.SIGNAL)
        self.app.audio_source.stop_recording.return_value = AudioDataResult(audio_data=[], sample_rate=16000)

        self.app.input_coordinator._handle_signal_channel("stop_recording")

        assert self.app.recording_coordinator._current_session is None
        self.app.audio_source.stop_recording.assert_called_once()

    def test_sigusr1_with_custom_mode(self):
        """Verify SIGUSR1 respects configured mode."""
        self.config.sigusr1_mode = "edit"

        self.app.input_coordinator._handle_signal_channel("mode_switch_1")

        self.app.transcription_service._handle_mode_change.assert_called_once_with("edit")

    def test_sigusr2_with_custom_mode(self):
        """Verify SIGUSR2 respects configured mode."""
        self.config.sigusr2_mode = "dictate"

        self.app.input_coordinator._handle_signal_channel("mode_switch_2")

        self.app.transcription_service._handle_mode_change.assert_called_once_with("dictate")

    def test_sigusr1_without_transcription_service(self):
        """Verify SIGUSR1 handles missing transcription service gracefully."""
        self.app.transcription_service = None
        self.app.recording_coordinator.transcription_service = None

        self.app.input_coordinator._handle_signal_channel("mode_switch_1")

        assert self.app.recording_coordinator._current_session is not None
        self.app.audio_source.start_recording.assert_called_once()

    def test_signal_handler_registration(self):
        """Verify all signal handlers are registered via bridge."""
        mock_qt_app = Mock()
        mock_bridge = Mock()
        mock_tray = Mock()

        with patch('input_coordinator.QApplication') as mock_qapp_class, \
             patch('input_coordinator.PosixSignalBridge') as mock_bridge_class, \
             patch('ui.SystemTrayUI') as mock_tray_class, \
             patch('input_coordinator.QSystemTrayIcon.isSystemTrayAvailable', return_value=True):

            mock_qapp_class.instance.return_value = mock_qt_app
            mock_bridge_class.return_value = mock_bridge
            mock_tray_class.return_value = mock_tray

            self.app.input_coordinator.setup_signal_handlers()

            calls = mock_bridge.register_signal.call_args_list
            assert len(calls) == 4
            assert any(call[0][0] == signal.SIGUSR1 for call in calls)
            assert any(call[0][0] == signal.SIGUSR2 for call in calls)
            assert any(call[0][0] == signal.SIGHUP for call in calls)
            assert any(call[0][0] == signal.SIGINT for call in calls)

    def test_mode_transition_resets_processor(self):
        """Verify mode transition triggers processor reset via existing mechanism."""
        self.app.transcription_service._handle_mode_change.return_value = True

        self.app.input_coordinator._handle_signal_channel("mode_switch_1")

        # Mode change handler should be called (it handles reset internally)
        self.app.transcription_service._handle_mode_change.assert_called_once()
