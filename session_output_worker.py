"""
EventQueue worker for sequential session output processing.
Processes transcription chunks and sends keyboard output.
"""
import queue
from processing_session import ProcessingSession
from lib.pr_log import pr_err, pr_info


def process_session_output(app, session: ProcessingSession):
    """
    Worker function that processes session chunks sequentially for keyboard output.

    This function is called by the EventQueue worker thread, ensuring that
    only one session outputs to the keyboard at a time.
    """
    if session.has_error:
        app.show_error_notification(session.error_message)
        return

    app.transcription_service.reset_streaming_state()

    while not session.chunks_complete.is_set() or not session.chunk_queue.empty():
        try:
            chunk = session.chunk_queue.get(timeout=0.1)
            app.transcription_service.process_streaming_chunk(chunk)
        except queue.Empty:
            continue
        except Exception as e:
            pr_err(f"Error processing chunk: {e}")

    app.transcription_service.complete_stream()

    final_text = app.transcription_service._build_current_text()
    if final_text:
        pr_info(f"{final_text}\n")
    else:
        pr_info("")

    if app.config.reset_state_each_response:
        app.transcription_service.reset_all_state()
