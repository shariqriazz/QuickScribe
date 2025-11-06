"""
Processing Coordinator - Orchestrates the two-queue processing pipeline.
"""
import threading
import time
import numpy as np
from typing import Optional
from recording_session import RecordingSession
from processing_session import ProcessingSession
from audio_source import AudioResult, AudioDataResult
from providers.conversation_context import ConversationContext
from lib.event_queue import EventQueue
from lib.pr_log import pr_info, pr_warn, pr_debug
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

        if not self._validate_audio_recording(session, result):
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

    def _validate_audio_recording(
        self,
        session: RecordingSession,
        result: AudioResult
    ) -> bool:
        """
        Validate audio recording meets minimum quality requirements.

        Checks:
        - Duration meets minimum threshold
        - Peak amplitude exceeds threshold
        - RMS peak over sliding window exceeds threshold

        Returns:
            True if recording is valid, False if should be discarded
        """
        if not isinstance(result, AudioDataResult):
            return True

        audio_data = result.audio_data
        sample_rate = result.sample_rate

        recording_duration = time.time() - session.start_time
        if recording_duration < self.config.min_recording_duration:
            pr_warn(f"Recording discarded: too short ({recording_duration:.2f}s < {self.config.min_recording_duration}s)")
            return False

        int16_max = 32767
        threshold = int(self.config.audio_amplitude_threshold * int16_max)
        abs_audio = np.abs(audio_data.flatten())
        peak_amplitude = np.max(abs_audio)

        if peak_amplitude < threshold:
            peak_percent = (peak_amplitude / int16_max) * 100
            threshold_percent = self.config.audio_amplitude_threshold * 100
            pr_warn(f"Recording discarded: amplitude too low ({peak_percent:.1f}% < {threshold_percent:.1f}%)")
            return False

        window_size = int(self.config.min_peak_duration * sample_rate)
        rms_threshold = int(self.config.min_peak_duration_amplitude_threshold * int16_max)

        if len(abs_audio) < window_size:
            pr_warn(f"Recording discarded: audio too short for RMS window analysis")
            return False

        audio_flat = audio_data.flatten().astype(np.float64)
        step_size = max(1, window_size // 10)

        num_windows = (len(audio_flat) - window_size) // step_size + 1
        rms_values = np.zeros(num_windows)

        for i in range(num_windows):
            start = i * step_size
            end = start + window_size
            window = audio_flat[start:end]
            rms_values[i] = np.sqrt(np.mean(window ** 2))

        peak_rms = np.max(rms_values)
        peak_rms_percent = (peak_rms / int16_max) * 100
        rms_threshold_percent = self.config.min_peak_duration_amplitude_threshold * 100

        if peak_rms < rms_threshold:
            pr_warn(f"Recording discarded: RMS peak too low ({peak_rms_percent:.1f}% < {rms_threshold_percent:.1f}%)")
            return False

        windows_above = np.sum(rms_values >= rms_threshold)
        pr_debug(f"Audio validation: duration={recording_duration:.2f}s peak={peak_amplitude} ({(peak_amplitude/int16_max)*100:.1f}%) rms={peak_rms:.1f} ({peak_rms_percent:.1f}%) windows={windows_above}/{len(rms_values)}")
        return True

    def shutdown(self):
        """Shutdown the session queue."""
        if self.session_queue:
            self.session_queue.shutdown()
