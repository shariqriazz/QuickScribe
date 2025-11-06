"""
Main dictation application using modular components.
"""
import sys
from config_manager import ConfigManager
from microphone_audio_source import MicrophoneAudioSource
from transcription_service import TranscriptionService
from providers.base_provider import BaseProvider
from ui import AppState
from lib.pr_log import pr_err, pr_warn, pr_notice, pr_info, pr_debug
from input_coordinator import InputCoordinator
from recording_coordinator import RecordingCoordinator
from processing_coordinator import ProcessingCoordinator

DTYPE = 'int16'
DEFAULT_SAMPLE_RATE = 16000
DEFAULT_CHANNELS = 1


class DictationApp:
    """Main dictation application orchestrator."""

    def __init__(self):
        self.config_manager = ConfigManager()
        self.config = None

        self.audio_source = None
        self.transcription_service = None
        self.provider = None

        self.input_coordinator = None
        self.recording_coordinator = None
        self.processing_coordinator = None
    
    def _return_to_idle(self) -> None:
        """Return to idle state with prompt."""
        self._update_tray_state(AppState.IDLE)
        self._show_recording_prompt()

    def _show_recording_prompt(self):
        """Show appropriate recording prompt based on trigger configuration."""
        if self.input_coordinator and self.input_coordinator.is_trigger_enabled():
            print(f"Hold '{self.config.trigger_key_name}' to record...")
        else:
            print("Keyboard trigger disabled. Use SIGUSR1 to start and SIGUSR2 to stop.")

    def _update_tray_state(self, new_state: AppState):
        """Update application state and notify system tray."""
        if self.input_coordinator and self.input_coordinator.system_tray:
            self.input_coordinator.system_tray.set_state(new_state)

    def _initialize_provider_client(self):
        """Initialize the provider client based on the selected provider."""
        try:
            # Pass audio_source to provider for instruction injection
            self.provider = BaseProvider(self.config, self.audio_source)

            # Provider should never be None now
            if self.provider is None:
                pr_err("No provider initialized")
                return False

            if self.provider.initialize():
                return True
            else:
                return False
        except ValueError as e:
            pr_err(f"{e}")
            return False
        except Exception as e:
            pr_err(f"Error initializing provider: {e}")
            return False

    def _initialize_services(self):
        """Initialize all service components."""
        self.transcription_service = TranscriptionService(self.config)
        return True

    def _initialize_coordinators(self):
        """Initialize coordinator components."""
        self.recording_coordinator = RecordingCoordinator(
            self.audio_source,
            self.transcription_service,
            self.config,
            self
        )

        self.processing_coordinator = ProcessingCoordinator(
            self.provider,
            self.transcription_service,
            self.config,
            self
        )
        if not self.processing_coordinator.initialize():
            return False

        self.input_coordinator = InputCoordinator(
            self.config,
            self.recording_coordinator,
            self.processing_coordinator,
            self
        )

        if not self.input_coordinator.setup_trigger_key():
            return False

        self.input_coordinator.setup_signal_handlers()
        return True
    
    
    def initialize(self):
        """Initialize all components."""
        from lib.pr_log import set_log_level, PR_DEBUG, PR_INFO

        if not self.config_manager.parse_configuration():
            return False
        self.config = self.config_manager

        if self.config.debug_enabled:
            set_log_level(PR_DEBUG)
        else:
            set_log_level(PR_INFO)

        if self.config.audio_source in ['transcribe', 'trans']:
            from transcription.factory import get_transcription_source
            try:
                self.audio_source = get_transcription_source(self.config)
            except RuntimeError as e:
                pr_err(f"{e}")
                return False
        else:
            self.audio_source = MicrophoneAudioSource(
                self.config,
                dtype=DTYPE
            )

        if not self.audio_source.initialize():
            return False

        if not self._initialize_provider_client():
            return False

        if not self._initialize_services():
            return False

        if not self._initialize_coordinators():
            return False

        return True
    
    def _display_configuration(self):
        """Display startup configuration."""
        pr_notice("--- Configuration ---")
        pr_info(f"Provider:      {self.config.provider.upper()}")
        pr_info(f"Model:         {self.config.model_id}")
        trigger_status = 'disabled' if not self.input_coordinator.is_trigger_enabled() else self.config.trigger_key_name
        pr_info(f"Trigger Key:   {trigger_status}")
        pr_info(f"Audio:         {self.config.sample_rate}Hz, {self.config.channels} channel(s)")
        if sys.platform == 'darwin':
            output_method = 'macOS Core Graphics'
        elif sys.platform.startswith('linux') or sys.platform.startswith('freebsd'):
            output_method = 'xdotool'
        elif sys.platform == 'win32':
            output_method = 'Windows SendInput'
        else:
            output_method = 'none (test mode)'
        pr_info(f"Output Method: {output_method}")
        if self.config.provider == 'groq' and self.config.language:
            pr_info(f"Language:      {self.config.language}")
        elif self.config.provider == 'gemini' and self.config.language:
            pr_info(f"Language:      '{self.config.language}' (Note: Ignored by Gemini)")
        pr_notice("--------------------")
        pr_notice("Ensure Terminal/IDE has Microphone and Accessibility/Input Monitoring permissions.")
        if self.config.provider == 'gemini':
            pr_notice("Note: Gemini currently only transcribes English audio well.")
        pr_notice("Press Ctrl+C to exit.")
    
    def _display_xml_instructions(self):
        """Display XML instructions for the model (only when -DD or higher)."""
        if not self.config.litellm_debug:
            return

        pr_debug("="*60)
        pr_debug("SYSTEM INSTRUCTIONS FOR MODEL:")
        pr_debug("-" * 60)
        xml_instructions = self.provider.get_xml_instructions()
        pr_debug(xml_instructions)
        pr_debug("="*60)
    
    def run(self):
        """Main application loop."""
        if not self.initialize():
            return 1

        self._display_configuration()
        self._display_xml_instructions()

        if self.input_coordinator.is_trigger_enabled():
            print(f"Hold '{self.config.trigger_key_name}' to record...")
        else:
            pr_notice(f"Keyboard trigger disabled. Signal controls:")
            pr_info(f"  SIGUSR1 → {self.config.sigusr1_mode} mode + start recording")
            pr_info(f"  SIGUSR2 → {self.config.sigusr2_mode} mode + start recording")
            pr_info(f"  SIGHUP  → stop recording")

        listener = None
        try:
            if self.input_coordinator.is_trigger_enabled():
                listener = self.input_coordinator.start_keyboard_listener()
                pr_debug(f"Keyboard listener started")

            if self.input_coordinator.qt_app:
                pr_debug(f"Starting Qt event loop (qt_app exists, listener={'exists' if listener else 'None'})")
                self.input_coordinator.qt_app.exec()
            elif listener:
                pr_debug("No Qt app, running keyboard listener loop")
                listener.join()
            else:
                pr_debug("No Qt app, no listener, running sleep loop")
                import time
                while True:
                    time.sleep(1)

        except Exception as e:
            pr_err(f"An unexpected error occurred in main execution: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.cleanup()
            return 0
    
    def cleanup(self):
        """Clean up resources."""
        pr_info("Cleaning up...")
        if self.processing_coordinator:
            self.processing_coordinator.shutdown()
        if self.input_coordinator:
            self.input_coordinator.cleanup()
        if self.audio_source:
            self.audio_source._cleanup()
        pr_info("Exited.")