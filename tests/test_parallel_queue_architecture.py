"""
Tests for two-queue parallel architecture.

Verifies:
- Parallel model invocation across multiple sessions
- Sequential keyboard output (no chunk interleaving)
- Per-session context isolation
- State management with --once flag
- Error handling and synchronization
"""
import unittest
import sys
import os
import queue
import threading
from unittest.mock import Mock, patch, MagicMock, call
from typing import List, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

sys.modules['pynput'] = Mock()
sys.modules['pynput.keyboard'] = Mock()

mock_qt = MagicMock()
sys.modules['PyQt6'] = mock_qt
sys.modules['PyQt6.QtWidgets'] = mock_qt.QtWidgets
sys.modules['PyQt6.QtCore'] = mock_qt.QtCore
sys.modules['PyQt6.QtGui'] = mock_qt.QtGui

from dictation_app import DictationApp, RecordingSession
from audio_source import AudioDataResult, AudioTextResult
from providers.conversation_context import ConversationContext


class MockConfig:
    """Mock configuration for testing."""
    def __init__(self):
        self.sample_rate = 16000
        self.channels = 1
        self.provider = "mock"
        self.model_id = "mock-model"
        self.trigger_key_name = None
        self.reset_state_each_response = False


class MockProvider:
    """Mock provider with controllable streaming behavior."""
    def __init__(self):
        self.transcribe_calls = []
        self.streaming_chunks = []
        self.invocation_started = threading.Event()
        self.call_count = 0

    def transcribe(self, context, audio_data=None, text_data=None,
                   streaming_callback=None, final_callback=None):
        self.invocation_started.set()
        call_info = {
            'context': context,
            'audio_data': audio_data,
            'text_data': text_data,
            'thread_id': threading.current_thread().ident
        }
        self.transcribe_calls.append(call_info)
        self.call_count += 1

        if streaming_callback and self.streaming_chunks:
            for chunk in self.streaming_chunks:
                streaming_callback(chunk)

    def initialize(self):
        return True

    def get_xml_instructions(self):
        return "Mock instructions"


class TestParallelModelInvocation(unittest.TestCase):
    """Test parallel model invocation across sessions."""

    def setUp(self):
        """Set up test fixtures."""
        self.config = MockConfig()

    @patch('dictation_app.signal', Mock())
    @patch('dictation_app.TranscriptionService')
    def test_parallel_session_recording(self, mock_transcription_service):
        """Verify multiple sessions invoke models in parallel threads."""
        app = DictationApp()
        app.config = self.config
        app.transcription_service = mock_transcription_service.return_value

        mock_provider = MockProvider()
        app.provider = mock_provider

        app._initialize_services()

        recording_threads = []

        for i in range(3):
            session = RecordingSession()
            session.context = ConversationContext(
                xml_markup=f"<session{i}/>",
                compiled_text=f"text{i}",
                sample_rate=16000
            )

            result = AudioTextResult(f"input{i}", 16000)
            thread = threading.Thread(
                target=app._record_to_session,
                args=(result, session)
            )
            recording_threads.append((thread, session))

        for thread, _ in recording_threads:
            thread.start()

        for thread, session in recording_threads:
            session.chunks_complete.wait(timeout=1.0)
            self.assertTrue(session.chunks_complete.is_set())

        for thread, _ in recording_threads:
            thread.join(timeout=1.0)

        self.assertEqual(len(mock_provider.transcribe_calls), 3)

        call_thread_ids = [call['thread_id'] for call in mock_provider.transcribe_calls]
        self.assertGreaterEqual(len(set(call_thread_ids)), 1)

        app.session_queue.shutdown()

    @patch('dictation_app.signal', Mock())
    @patch('dictation_app.TranscriptionService')
    def test_session_context_isolation(self, mock_transcription_service):
        """Verify each session has frozen conversation context."""
        app = DictationApp()
        app.config = self.config

        mock_transcription = mock_transcription_service.return_value
        mock_transcription._build_xml_from_processor.return_value = "<context_a/>"
        mock_transcription._build_current_text.return_value = "text_a"
        app.transcription_service = mock_transcription

        mock_provider = MockProvider()
        app.provider = mock_provider

        app._initialize_services()

        session1 = RecordingSession()
        session1.context = app._get_conversation_context()

        mock_transcription._build_xml_from_processor.return_value = "<context_b/>"
        mock_transcription._build_current_text.return_value = "text_b"

        session2 = RecordingSession()
        session2.context = app._get_conversation_context()

        result1 = AudioTextResult("input1", 16000)
        thread1 = threading.Thread(target=app._record_to_session, args=(result1, session1))
        thread1.start()

        result2 = AudioTextResult("input2", 16000)
        thread2 = threading.Thread(target=app._record_to_session, args=(result2, session2))
        thread2.start()

        thread1.join(timeout=1.0)
        thread2.join(timeout=1.0)

        self.assertEqual(len(mock_provider.transcribe_calls), 2)

        context1 = mock_provider.transcribe_calls[0]['context']
        context2 = mock_provider.transcribe_calls[1]['context']

        self.assertEqual(context1.xml_markup, "<context_a/>")
        self.assertEqual(context1.compiled_text, "text_a")
        self.assertEqual(context2.xml_markup, "<context_b/>")
        self.assertEqual(context2.compiled_text, "text_b")

        app.session_queue.shutdown()


class TestSequentialOutput(unittest.TestCase):
    """Test sequential keyboard output processing."""

    def setUp(self):
        """Set up test fixtures."""
        self.config = MockConfig()

    @patch('dictation_app.signal', Mock())
    @patch('dictation_app.TranscriptionService')
    def test_sequential_keyboard_output(self, mock_transcription_service):
        """Verify keyboard output is serialized (no chunk interleaving)."""
        app = DictationApp()
        app.config = self.config

        mock_transcription = mock_transcription_service.return_value
        mock_transcription.process_streaming_chunk = Mock()
        mock_transcription.complete_stream = Mock()
        mock_transcription._build_current_text.return_value = "output"
        app.transcription_service = mock_transcription

        chunk_order = []
        original_process_chunk = mock_transcription.process_streaming_chunk

        def track_chunks(chunk):
            chunk_order.append(chunk)
            original_process_chunk(chunk)

        mock_transcription.process_streaming_chunk = track_chunks

        app._initialize_services()

        session1 = RecordingSession()
        session1.chunk_queue.put("A1")
        session1.chunk_queue.put("A2")
        session1.chunks_complete.set()

        session2 = RecordingSession()
        session2.chunk_queue.put("B1")
        session2.chunk_queue.put("B2")
        session2.chunks_complete.set()

        session3 = RecordingSession()
        session3.chunk_queue.put("C1")
        session3.chunk_queue.put("C2")
        session3.chunks_complete.set()

        app.session_queue.enqueue(session1)
        app.session_queue.enqueue(session2)
        app.session_queue.enqueue(session3)

        completed = threading.Event()
        original_processor = app.session_queue._processor

        def track_completion(session):
            original_processor(session)
            if session == session3:
                completed.set()

        app.session_queue._processor = track_completion

        completed.wait(timeout=2.0)
        self.assertTrue(completed.is_set())

        self.assertEqual(chunk_order, ["A1", "A2", "B1", "B2", "C1", "C2"])

        app.session_queue.shutdown()

    @patch('dictation_app.signal', Mock())
    @patch('dictation_app.TranscriptionService')
    def test_blocking_chunk_consumption(self, mock_transcription_service):
        """Verify real-time streaming within session (no bulk processing)."""
        app = DictationApp()
        app.config = self.config

        mock_transcription = mock_transcription_service.return_value
        chunk_events = {}

        def record_chunk_event(chunk):
            chunk_events[chunk] = threading.Event()
            chunk_events[chunk].set()

        mock_transcription.process_streaming_chunk = record_chunk_event
        mock_transcription.complete_stream = Mock()
        mock_transcription._build_current_text.return_value = "output"
        app.transcription_service = mock_transcription

        app._initialize_services()

        session = RecordingSession()
        chunk1_queued = threading.Event()
        chunk2_queued = threading.Event()
        chunk3_queued = threading.Event()

        def queue_chunks():
            session.chunk_queue.put("chunk1")
            chunk1_queued.set()
            session.chunk_queue.put("chunk2")
            chunk2_queued.set()
            session.chunk_queue.put("chunk3")
            chunk3_queued.set()
            session.chunks_complete.set()

        chunk_thread = threading.Thread(target=queue_chunks)
        chunk_thread.start()

        app.session_queue.enqueue(session)

        chunk1_queued.wait(timeout=1.0)
        if "chunk1" in chunk_events:
            chunk_events["chunk1"].wait(timeout=1.0)

        chunk2_queued.wait(timeout=1.0)
        if "chunk2" in chunk_events:
            chunk_events["chunk2"].wait(timeout=1.0)

        chunk_thread.join(timeout=1.0)

        processing_complete = threading.Event()
        original_processor = app.session_queue._processor

        def signal_completion(session_arg):
            original_processor(session_arg)
            processing_complete.set()

        app.session_queue._processor = signal_completion
        processing_complete.wait(timeout=1.0)

        self.assertEqual(len(chunk_events), 3)
        self.assertIn("chunk1", chunk_events)
        self.assertIn("chunk2", chunk_events)
        self.assertIn("chunk3", chunk_events)

        app.session_queue.shutdown()


class TestStateManagement(unittest.TestCase):
    """Test state management with --once flag."""

    def setUp(self):
        """Set up test fixtures."""
        self.config = MockConfig()

    @patch('dictation_app.signal', Mock())
    @patch('dictation_app.TranscriptionService')
    def test_reset_state_each_response(self, mock_transcription_service):
        """Verify --once flag resets processor state after each session."""
        app = DictationApp()
        app.config = self.config
        app.config.reset_state_each_response = True

        mock_transcription = mock_transcription_service.return_value
        mock_transcription.reset_streaming_state = Mock()
        mock_transcription.complete_stream = Mock()
        mock_transcription.reset_all_state = Mock()
        mock_transcription._build_current_text.return_value = "output"
        app.transcription_service = mock_transcription

        app._initialize_services()

        session1 = RecordingSession()
        session1.chunk_queue.put("chunk1")
        session1.chunks_complete.set()

        session2 = RecordingSession()
        session2.chunk_queue.put("chunk2")
        session2.chunks_complete.set()

        app.session_queue.enqueue(session1)
        app.session_queue.enqueue(session2)

        completed = threading.Event()
        original_processor = app.session_queue._processor

        def track_completion(session):
            original_processor(session)
            if session == session2:
                completed.set()

        app.session_queue._processor = track_completion

        completed.wait(timeout=2.0)
        self.assertTrue(completed.is_set())

        self.assertEqual(mock_transcription.reset_all_state.call_count, 2)

        app.session_queue.shutdown()

    @patch('dictation_app.signal', Mock())
    @patch('dictation_app.TranscriptionService')
    def test_persistent_state_across_sessions(self, mock_transcription_service):
        """Verify default behavior preserves state across sessions."""
        app = DictationApp()
        app.config = self.config
        app.config.reset_state_each_response = False

        mock_transcription = mock_transcription_service.return_value
        mock_transcription.reset_streaming_state = Mock()
        mock_transcription.complete_stream = Mock()
        mock_transcription.reset_all_state = Mock()
        mock_transcription._build_xml_from_processor.return_value = "<prev/>"
        mock_transcription._build_current_text.return_value = "previous text"
        app.transcription_service = mock_transcription

        app._initialize_services()

        session1 = RecordingSession()
        session1.context = app._get_conversation_context()
        session1.chunk_queue.put("chunk1")
        session1.chunks_complete.set()

        session1_complete = threading.Event()
        original_processor = app.session_queue._processor

        def track_session1(session):
            original_processor(session)
            if session == session1:
                session1_complete.set()

        app.session_queue._processor = track_session1

        app.session_queue.enqueue(session1)

        session1_complete.wait(timeout=1.0)
        self.assertTrue(session1_complete.is_set())

        mock_transcription._build_xml_from_processor.return_value = "<prev/><session1/>"
        mock_transcription._build_current_text.return_value = "previous text session1"

        session2 = RecordingSession()
        session2.context = app._get_conversation_context()

        self.assertIn("<session1/>", session2.context.xml_markup)
        self.assertIn("session1", session2.context.compiled_text)

        self.assertEqual(mock_transcription.reset_all_state.call_count, 0)

        app.session_queue.shutdown()


class TestErrorHandling(unittest.TestCase):
    """Test error handling in parallel architecture."""

    def setUp(self):
        """Set up test fixtures."""
        self.config = MockConfig()

    @patch('dictation_app.signal', Mock())
    @patch('dictation_app.TranscriptionService')
    def test_session_error_does_not_block_queue(self, mock_transcription_service):
        """Verify exception in one session doesn't halt processing."""
        app = DictationApp()
        app.config = self.config

        mock_transcription = mock_transcription_service.return_value
        mock_transcription.process_streaming_chunk = Mock()
        mock_transcription.complete_stream = Mock()
        mock_transcription._build_current_text.return_value = "output"
        app.transcription_service = mock_transcription

        failing_provider = Mock()
        failing_provider.transcribe.side_effect = RuntimeError("Model error")
        app.provider = failing_provider

        app._initialize_services()

        session1 = RecordingSession()
        session1.context = ConversationContext("", "", 16000)
        result1 = AudioTextResult("input1", 16000)

        thread1 = threading.Thread(target=app._record_to_session, args=(result1, session1))
        thread1.start()
        thread1.join(timeout=1.0)

        self.assertTrue(session1.chunks_complete.is_set())

        working_provider = MockProvider()
        working_provider.streaming_chunks = ["chunk2"]
        app.provider = working_provider

        session2 = RecordingSession()
        session2.context = ConversationContext("", "", 16000)
        result2 = AudioTextResult("input2", 16000)

        thread2 = threading.Thread(target=app._record_to_session, args=(result2, session2))
        thread2.start()
        thread2.join(timeout=1.0)

        self.assertTrue(session2.chunks_complete.is_set())
        self.assertEqual(len(working_provider.transcribe_calls), 1)

        app.session_queue.shutdown()

    @patch('dictation_app.signal', Mock())
    @patch('dictation_app.TranscriptionService')
    def test_empty_chunk_queue_handling(self, mock_transcription_service):
        """Verify queue.Empty exception handling during processing."""
        app = DictationApp()
        app.config = self.config

        mock_transcription = mock_transcription_service.return_value
        chunks_processed = []

        def track_chunk(chunk):
            chunks_processed.append(chunk)

        mock_transcription.process_streaming_chunk = track_chunk
        mock_transcription.complete_stream = Mock()
        mock_transcription._build_current_text.return_value = "output"
        app.transcription_service = mock_transcription

        app._initialize_services()

        session = RecordingSession()
        chunk_ready = threading.Event()

        def delayed_completion():
            chunk_ready.wait()
            session.chunk_queue.put("delayed_chunk")
            session.chunks_complete.set()

        completion_thread = threading.Thread(target=delayed_completion)
        completion_thread.start()

        processing_complete = threading.Event()
        original_processor = app.session_queue._processor

        def track_processing(session_arg):
            chunk_ready.set()
            original_processor(session_arg)
            processing_complete.set()

        app.session_queue._processor = track_processing

        app.session_queue.enqueue(session)

        processing_complete.wait(timeout=1.0)
        completion_thread.join(timeout=1.0)

        self.assertIn("delayed_chunk", chunks_processed)

        app.session_queue.shutdown()


class TestSynchronization(unittest.TestCase):
    """Test synchronization primitives in architecture."""

    def setUp(self):
        """Set up test fixtures."""
        self.config = MockConfig()

    @patch('dictation_app.signal', Mock())
    @patch('dictation_app.TranscriptionService')
    def test_chunks_complete_event(self, mock_transcription_service):
        """Verify chunks_complete event synchronization."""
        app = DictationApp()
        app.config = self.config

        mock_transcription = mock_transcription_service.return_value
        chunks_processed = []

        def track_chunk(chunk):
            chunks_processed.append(chunk)

        mock_transcription.process_streaming_chunk = track_chunk
        mock_transcription.complete_stream = Mock()
        mock_transcription._build_current_text.return_value = "output"
        app.transcription_service = mock_transcription

        app._initialize_services()

        session = RecordingSession()
        chunk1_ready = threading.Event()
        chunk2_ready = threading.Event()

        def stream_chunks():
            chunk1_ready.wait()
            session.chunk_queue.put("chunk1")
            chunk2_ready.wait()
            session.chunk_queue.put("chunk2")
            session.chunks_complete.set()

        stream_thread = threading.Thread(target=stream_chunks)
        stream_thread.start()

        processing_complete = threading.Event()
        original_processor = app.session_queue._processor

        def track_processing(session_arg):
            chunk1_ready.set()
            chunk2_ready.set()
            original_processor(session_arg)
            processing_complete.set()

        app.session_queue._processor = track_processing

        app.session_queue.enqueue(session)

        processing_complete.wait(timeout=1.0)
        stream_thread.join(timeout=1.0)

        self.assertEqual(chunks_processed, ["chunk1", "chunk2"])

        app.session_queue.shutdown()

    @patch('dictation_app.signal', Mock())
    @patch('dictation_app.TranscriptionService')
    def test_session_queue_ordering(self, mock_transcription_service):
        """Verify FIFO session processing order."""
        app = DictationApp()
        app.config = self.config

        mock_transcription = mock_transcription_service.return_value
        mock_transcription.reset_streaming_state = Mock()
        mock_transcription.complete_stream = Mock()
        mock_transcription._build_current_text.return_value = "output"
        app.transcription_service = mock_transcription

        app._initialize_services()

        execution_order = []

        session_a = RecordingSession()
        session_a.name = "A"
        session_a.chunks_complete.set()

        session_b = RecordingSession()
        session_b.name = "B"
        session_b.chunks_complete.set()

        session_c = RecordingSession()
        session_c.name = "C"
        session_c.chunks_complete.set()

        all_complete = threading.Event()
        original_processor = app._process_session_output

        def track_execution(session):
            execution_order.append(session.name)
            original_processor(session)
            if session == session_c:
                all_complete.set()

        app.session_queue._processor = track_execution

        app.session_queue.enqueue(session_a)
        app.session_queue.enqueue(session_b)
        app.session_queue.enqueue(session_c)

        all_complete.wait(timeout=2.0)
        self.assertTrue(all_complete.is_set())

        self.assertEqual(execution_order, ["A", "B", "C"])

        app.session_queue.shutdown()


class TestEndToEndIntegration(unittest.TestCase):
    """End-to-end integration tests for parallel architecture."""

    def setUp(self):
        """Set up test fixtures."""
        self.config = MockConfig()

    @patch('dictation_app.signal', Mock())
    @patch('dictation_app.TranscriptionService')
    def test_end_to_end_parallel_flow(self, mock_transcription_service):
        """Complete workflow: parallel model invocation, sequential output."""
        app = DictationApp()
        app.config = self.config

        mock_transcription = mock_transcription_service.return_value
        output_order = []

        def track_output(chunk):
            output_order.append(chunk)

        mock_transcription.process_streaming_chunk = track_output
        mock_transcription.complete_stream = Mock()
        mock_transcription._build_current_text.return_value = "output"
        app.transcription_service = mock_transcription

        mock_provider = MockProvider()
        mock_provider.streaming_chunks = ["1A", "1B", "1C", "2A", "2B"]
        app.provider = mock_provider

        app._initialize_services()

        session1 = RecordingSession()
        session1.context = ConversationContext("", "", 16000)
        result1 = AudioTextResult("input1", 16000)

        session2 = RecordingSession()
        session2.context = ConversationContext("", "", 16000)
        result2 = AudioTextResult("input2", 16000)

        thread1 = threading.Thread(target=app._record_to_session, args=(result1, session1))
        thread2 = threading.Thread(target=app._record_to_session, args=(result2, session2))

        thread1.start()
        thread2.start()

        thread1.join(timeout=1.0)
        thread2.join(timeout=1.0)

        self.assertTrue(session1.chunks_complete.is_set())
        self.assertTrue(session2.chunks_complete.is_set())

        all_processed = threading.Event()
        original_processor = app.session_queue._processor

        def track_completion(session):
            original_processor(session)
            if session == session2:
                all_processed.set()

        app.session_queue._processor = track_completion

        app.session_queue.enqueue(session1)
        app.session_queue.enqueue(session2)

        all_processed.wait(timeout=2.0)
        self.assertTrue(all_processed.is_set())

        self.assertGreaterEqual(len(output_order), 5)
        self.assertTrue(all(chunk in ["1A", "1B", "1C", "2A", "2B"] for chunk in output_order))

        app.session_queue.shutdown()


def run_parallel_queue_tests():
    """Run all parallel queue architecture tests."""
    print("Running Parallel Queue Architecture Tests")
    print("=" * 60)

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    test_classes = [
        TestParallelModelInvocation,
        TestSequentialOutput,
        TestStateManagement,
        TestErrorHandling,
        TestSynchronization,
        TestEndToEndIntegration
    ]

    for test_class in test_classes:
        tests = loader.loadTestsFromTestCase(test_class)
        suite.addTests(tests)

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("\n" + "=" * 60)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")

    if result.failures:
        print("\nFailures:")
        for test, traceback in result.failures:
            print(f"  - {test}")
            print(f"    {traceback}")

    if result.errors:
        print("\nErrors:")
        for test, traceback in result.errors:
            print(f"  - {test}")
            print(f"    {traceback}")

    return len(result.failures) == 0 and len(result.errors) == 0


if __name__ == "__main__":
    success = run_parallel_queue_tests()
    sys.exit(0 if success else 1)
