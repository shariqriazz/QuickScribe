"""
Thread worker for model invocation.
Runs in parallel to invoke transcription models asynchronously.
"""
from typing import Optional
from processing_session import ProcessingSession
from audio_source import AudioResult, AudioDataResult, AudioTextResult
from lib.pr_log import pr_err


def invoke_model_for_session(provider, session: ProcessingSession, result: AudioResult):
    """
    Thread worker that invokes model and writes chunks to session queue.

    This function runs in a daemon thread spawned by ProcessingCoordinator.
    It routes the audio result to the appropriate model invocation based on type.
    """
    if not provider:
        session.chunks_complete.set()
        return

    try:
        if isinstance(result, AudioDataResult):
            _invoke_model(provider, session, audio_data=result.audio_data)
        elif isinstance(result, AudioTextResult):
            _invoke_model(provider, session, text_data=result.transcribed_text)
        else:
            pr_err(f"Unsupported audio result type: {type(result)}")
            session.chunks_complete.set()
    except Exception as e:
        pr_err(f"Error in invoke_model_for_session: {e}")
        session.chunks_complete.set()


def _invoke_model(provider, session: ProcessingSession, audio_data=None, text_data=None):
    """Invoke model with streaming callback that collects chunks to session queue."""
    def streaming_callback(chunk_text):
        session.chunk_queue.put(chunk_text)

    try:
        provider.transcribe(
            session.context,
            audio_data=audio_data,
            text_data=text_data,
            streaming_callback=streaming_callback,
            final_callback=None
        )
    finally:
        session.chunks_complete.set()
