"""
XDotool Queue - Serializes xdotool operations to prevent mid-splice corruption.
"""

import time
from typing import List, Optional, Callable, Union
from dataclasses import dataclass
from queue import Queue
import threading

# Try to import XdotoolError, but handle case where we're using mock
try:
    from .output_manager import OutputManager, XdotoolError
except ImportError:
    # For testing, XdotoolError might not be available
    class XdotoolError(Exception):
        pass


@dataclass
class QueuedOperation:
    """Represents a queued xdotool operation."""
    operation_type: str  # 'backspace_and_type'
    backspaces: int
    text: str
    queued_at: float


class XdotoolQueue:
    """
    Manages a queue of xdotool operations to prevent concurrent execution.
    
    Ensures operations are executed atomically and tracks actual cursor position.
    """
    
    def __init__(self, output_manager):
        """
        Initialize xdotool queue.
        
        Args:
            output_manager: OutputManager instance (or MockOutputManager) for executing xdotool commands
        """
        self.output_manager = output_manager
        self.operation_queue: Queue = Queue()
        self.is_executing = False
        self.current_cursor_position = 0
        self.processing_thread: Optional[threading.Thread] = None
        self.should_stop = False
        
    def queue_backspace_and_type(self, backspaces: int, text: str) -> None:
        """
        Queue a backspace and type operation.
        
        Args:
            backspaces: Number of characters to backspace
            text: Text to type after backspacing
        """
        operation = QueuedOperation(
            operation_type='backspace_and_type',
            backspaces=backspaces,
            text=text,
            queued_at=time.time()
        )
        
        self.operation_queue.put(operation)
        self._start_processing_if_needed()
    
    def queue_type(self, text: str) -> None:
        """
        Queue a type-only operation (no backspacing).
        
        Args:
            text: Text to type
        """
        operation = QueuedOperation(
            operation_type='backspace_and_type',
            backspaces=0,
            text=text,
            queued_at=time.time()
        )
        
        self.operation_queue.put(operation)
        self._start_processing_if_needed()
    
    def _start_processing_if_needed(self) -> None:
        """Start processing thread if not already running."""
        if self.processing_thread is None or not self.processing_thread.is_alive():
            self.processing_thread = threading.Thread(target=self._process_queue, daemon=True)
            self.processing_thread.start()
    
    def _process_queue(self) -> None:
        """Process queued operations in order."""
        while not self.should_stop:
            try:
                # Get next operation with timeout
                operation = self.operation_queue.get(timeout=1.0)
                
                # Mark as executing
                self.is_executing = True
                
                try:
                    self._execute_operation(operation)
                except (XdotoolError, AttributeError) as e:
                    # AttributeError might occur with mock objects
                    print(f"XdotoolQueue: Operation failed: {e}")
                finally:
                    self.is_executing = False
                    self.operation_queue.task_done()
                    
            except:  # Queue timeout or other exception
                # No more operations to process
                break
    
    def _execute_operation(self, operation: QueuedOperation) -> None:
        """
        Execute a single operation atomically.
        
        Args:
            operation: Operation to execute
        """
        if operation.operation_type == 'backspace_and_type':
            # Execute backspaces
            if operation.backspaces > 0:
                self.output_manager.backspace(operation.backspaces)
                # Update cursor position
                self.current_cursor_position = max(0, self.current_cursor_position - operation.backspaces)
            
            # Execute typing
            if operation.text:
                self.output_manager.type_text(operation.text)
                # Update cursor position
                self.current_cursor_position += len(operation.text)
    
    def get_cursor_position(self) -> int:
        """
        Get current cursor position.
        
        Returns:
            Current cursor position in characters
        """
        return self.current_cursor_position
    
    def set_cursor_position(self, position: int) -> None:
        """
        Set cursor position (for initialization or reset).
        
        Args:
            position: New cursor position
        """
        self.current_cursor_position = position
    
    def is_busy(self) -> bool:
        """
        Check if queue is currently executing operations.
        
        Returns:
            True if operations are being executed
        """
        return self.is_executing or not self.operation_queue.empty()
    
    def wait_for_completion(self, timeout: float = 5.0) -> bool:
        """
        Wait for all queued operations to complete.
        
        Args:
            timeout: Maximum time to wait in seconds
            
        Returns:
            True if completed, False if timeout
        """
        start_time = time.time()
        while self.is_busy() and (time.time() - start_time) < timeout:
            time.sleep(0.01)
        return not self.is_busy()
    
    def clear_queue(self) -> None:
        """Clear all pending operations."""
        while not self.operation_queue.empty():
            try:
                self.operation_queue.get_nowait()
                self.operation_queue.task_done()
            except:
                break
    
    def stop(self) -> None:
        """Stop the processing thread."""
        self.should_stop = True
        if self.processing_thread and self.processing_thread.is_alive():
            self.processing_thread.join(timeout=1.0)
    
    def reset(self) -> None:
        """Reset queue state."""
        self.clear_queue()
        self.current_cursor_position = 0
        self.is_executing = False