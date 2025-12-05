"""Generic event-driven queue processor for sequential task execution."""

import queue
import threading
from typing import Callable, Any, Optional
from lib.pr_log import pr_debug, pr_warn


class EventQueue:
    """
    Thread-safe event-driven queue processor.

    Processes queued items sequentially in a dedicated worker thread.
    Uses event-based signaling to avoid polling.
    """

    def __init__(self, processor_callback: Callable[[Any], None], name: str = "EventQueue"):
        """
        Initialize event queue.

        Args:
            processor_callback: Function to process each queued item
            name: Descriptive name for logging and debugging
        """
        if not callable(processor_callback):
            raise TypeError("processor_callback must be callable")
        if not name or not isinstance(name, str):
            raise TypeError("name must be non-empty string")

        self._processor = processor_callback
        self._name = name
        self._queue = queue.Queue()
        self._wake_event = threading.Event()
        self._shutdown_event = threading.Event()
        self._worker_thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """Start the worker thread."""
        if self._worker_thread is not None and self._worker_thread.is_alive():
            pr_warn(f"{self._name}: Worker thread already running")
            return

        self._shutdown_event.clear()
        self._worker_thread = threading.Thread(
            target=self._worker_loop,
            name=f"{self._name}-Worker",
            daemon=True
        )
        self._worker_thread.start()
        pr_debug(f"{self._name}: Worker thread started")

    def enqueue(self, item: Any) -> None:
        """
        Add item to queue and signal worker.

        Args:
            item: Item to be processed by callback
        """
        self._queue.put(item)
        self._wake_event.set()
        pr_debug(f"{self._name}: Item enqueued, queue size={self._queue.qsize()}")

    def shutdown(self, timeout: float = 2.0) -> None:
        """
        Stop worker thread gracefully.

        Args:
            timeout: Maximum seconds to wait for worker to finish
        """
        if self._worker_thread is None:
            return
        if not self._worker_thread.is_alive():
            return

        pr_debug(f"{self._name}: Initiating shutdown")
        self._shutdown_event.set()
        self._wake_event.set()

        self._worker_thread.join(timeout=timeout)
        if self._worker_thread.is_alive():
            pr_warn(f"{self._name}: Worker thread did not terminate within {timeout}s")
        else:
            pr_debug(f"{self._name}: Worker thread terminated")

    def is_running(self) -> bool:
        """Check if worker thread is active."""
        if self._worker_thread is None:
            return False
        return self._worker_thread.is_alive()

    def _worker_loop(self) -> None:
        """Worker thread main loop - processes queued items sequentially."""
        pr_debug(f"{self._name}: Worker loop started")

        while not self._shutdown_event.is_set():
            self._wake_event.wait(timeout=1.0)

            if self._shutdown_event.is_set():
                break

            while not self._queue.empty():
                if self._shutdown_event.is_set():
                    break

                try:
                    item = self._queue.get_nowait()
                    pr_debug(f"{self._name}: Processing item")
                    self._processor(item)
                    self._queue.task_done()
                except queue.Empty:
                    break
                except Exception as e:
                    pr_warn(f"{self._name}: Error processing item: {e}")
                    import traceback
                    traceback.print_exc()

            self._wake_event.clear()

        pr_debug(f"{self._name}: Worker loop exited")
