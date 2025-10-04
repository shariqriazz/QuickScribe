"""Tests for signal handler functionality."""
import pytest
import signal
from unittest.mock import Mock, patch, MagicMock
from dictation_app import DictationApp
from config_manager import ConfigManager


class TestSignalHandlers:
    """Test signal handler behavior."""

    def setup_method(self):
        """Setup test fixtures."""
        self.config = ConfigManager()
        self.config.sigusr1_mode = "dictate"
        self.config.sigusr2_mode = "shell"
        self.app = DictationApp()
        self.app.config = self.config
        self.app.transcription_service = Mock()
        self.app.audio_source = Mock()
        self.app._is_recording = False

    def test_sigusr1_switches_mode_and_starts_recording(self):
        """Verify SIGUSR1 switches to sigusr1_mode and starts recording."""
        self.app.handle_sigusr1(signal.SIGUSR1, None)

        self.app.transcription_service._handle_mode_change.assert_called_once_with("dictate")
        assert self.app._is_recording == True
        self.app.audio_source.start_recording.assert_called_once()

    def test_sigusr2_switches_mode_and_starts_recording(self):
        """Verify SIGUSR2 switches to sigusr2_mode and starts recording."""
        self.app.handle_sigusr2(signal.SIGUSR2, None)

        self.app.transcription_service._handle_mode_change.assert_called_once_with("shell")
        assert self.app._is_recording == True
        self.app.audio_source.start_recording.assert_called_once()

    def test_sighup_stops_recording(self):
        """Verify SIGHUP stops recording."""
        self.app._is_recording = True
        self.app.audio_source.stop_recording.return_value = Mock(audio_data=[])

        self.app.handle_sighup(signal.SIGHUP, None)

        assert self.app._is_recording == False
        self.app.audio_source.stop_recording.assert_called_once()

    def test_sigusr1_with_custom_mode(self):
        """Verify SIGUSR1 respects configured mode."""
        self.config.sigusr1_mode = "edit"

        self.app.handle_sigusr1(signal.SIGUSR1, None)

        self.app.transcription_service._handle_mode_change.assert_called_once_with("edit")

    def test_sigusr2_with_custom_mode(self):
        """Verify SIGUSR2 respects configured mode."""
        self.config.sigusr2_mode = "dictate"

        self.app.handle_sigusr2(signal.SIGUSR2, None)

        self.app.transcription_service._handle_mode_change.assert_called_once_with("dictate")

    def test_sigusr1_without_transcription_service(self):
        """Verify SIGUSR1 handles missing transcription service gracefully."""
        self.app.transcription_service = None

        self.app.handle_sigusr1(signal.SIGUSR1, None)

        assert self.app._is_recording == True
        self.app.audio_source.start_recording.assert_called_once()

    def test_signal_handler_registration(self):
        """Verify all three signal handlers are registered."""
        with patch('signal.signal') as mock_signal:
            self.app.setup_signal_handlers()

            calls = mock_signal.call_args_list
            assert len(calls) == 3
            assert any(call[0][0] == signal.SIGUSR1 for call in calls)
            assert any(call[0][0] == signal.SIGUSR2 for call in calls)
            assert any(call[0][0] == signal.SIGHUP for call in calls)

    def test_mode_transition_resets_processor(self):
        """Verify mode transition triggers processor reset via existing mechanism."""
        self.app.transcription_service._handle_mode_change.return_value = True

        self.app.handle_sigusr1(signal.SIGUSR1, None)

        # Mode change handler should be called (it handles reset internally)
        self.app.transcription_service._handle_mode_change.assert_called_once()
