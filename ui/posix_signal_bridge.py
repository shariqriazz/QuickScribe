"""
Abstract bridge between POSIX signals and Qt event system.

Provides a clean, event-based integration that hides low-level socket
implementation details behind descriptive channel names.
"""

import signal
import socket
import sys
import os
from typing import Dict, List, Callable, Optional
from PyQt6.QtCore import QObject, QSocketNotifier, pyqtSignal


class SignalChannel:
    """
    Encapsulates one POSIX signal's communication pathway.

    Each channel represents a named event source that bridges a POSIX
    signal to Qt's event system through an internal socket pair.
    """

    def __init__(self, signal_number: int, channel_name: str):
        self.signal_number = signal_number
        self.channel_name = channel_name
        self.write_endpoint: Optional[socket.socket] = None
        self.read_endpoint: Optional[socket.socket] = None
        self.qt_notifier: Optional[QSocketNotifier] = None

    def create_endpoints(self) -> bool:
        """
        Create internal communication endpoints.

        Returns:
            True if successful, False on error
        """
        try:
            self.write_endpoint, self.read_endpoint = socket.socketpair()
            self.write_endpoint.setblocking(False)
            self.read_endpoint.setblocking(False)
            return True
        except OSError as e:
            print(f"Failed to create signal channel '{self.channel_name}': {e}",
                  file=sys.stderr)
            return False

    def notify_received(self):
        """
        Signal that POSIX signal was received.

        Called from POSIX signal handler context.
        Must be async-signal-safe.
        """
        if self.write_endpoint:
            try:
                self.write_endpoint.send(b'\x00')
            except (BlockingIOError, OSError):
                pass

    def drain(self):
        """
        Drain the notification from the channel.

        Called from Qt event loop context after detection.
        """
        if self.read_endpoint:
            try:
                self.read_endpoint.recv(1)
            except (BlockingIOError, OSError):
                pass

    def cleanup(self):
        """Release channel resources."""
        if self.write_endpoint:
            self.write_endpoint.close()
        if self.read_endpoint:
            self.read_endpoint.close()


class SignalRouter:
    """
    Routes POSIX signals to registered channels.

    Maintains global registry since POSIX signal handlers must be
    static functions at the process level.
    """

    _channel_map: Dict[int, List[SignalChannel]] = {}
    _wakeup_pipe_read: int = -1
    _wakeup_pipe_write: int = -1

    @classmethod
    def _setup_wakeup_pipe(cls):
        """Setup wakeup pipe to ensure Python processes signals during Qt event loop."""
        if cls._wakeup_pipe_read >= 0:
            return  # Already setup

        cls._wakeup_pipe_read, cls._wakeup_pipe_write = os.pipe()
        os.set_blocking(cls._wakeup_pipe_read, False)
        os.set_blocking(cls._wakeup_pipe_write, False)

        old_wakeup = signal.set_wakeup_fd(cls._wakeup_pipe_write)
        print(f"Set signal wakeup fd to {cls._wakeup_pipe_write}, old: {old_wakeup}", file=sys.stderr)

    @classmethod
    def register_channel(cls, channel: SignalChannel) -> bool:
        """
        Register a channel to receive POSIX signal notifications.

        Args:
            channel: The SignalChannel to register

        Returns:
            True if registered successfully
        """
        sig_num = channel.signal_number

        # Setup wakeup pipe on first registration
        cls._setup_wakeup_pipe()

        if sig_num not in cls._channel_map:
            cls._channel_map[sig_num] = []
            try:
                old_handler = signal.signal(sig_num, cls._posix_handler)
                print(f"Installed signal handler for {sig_num}, replaced: {old_handler}", file=sys.stderr)
            except (ValueError, OSError) as e:
                print(f"Failed to install handler for signal {sig_num}: {e}",
                      file=sys.stderr)
                return False

        cls._channel_map[sig_num].append(channel)
        return True

    @classmethod
    def _posix_handler(cls, signum: int, frame):
        """
        POSIX signal handler.

        Routes signal to all registered channels.
        Must be async-signal-safe.
        """
        if signum in cls._channel_map:
            for channel in cls._channel_map[signum]:
                channel.notify_received()


class PosixSignalBridge(QObject):
    """
    Bridges POSIX signals to Qt signals through named channels.

    Example:
        bridge = PosixSignalBridge()
        bridge.register_signal(signal.SIGHUP, "reload_config")
        bridge.signal_received.connect(handle_signal)

        def handle_signal(channel_name: str):
            if channel_name == "reload_config":
                reload_configuration()
    """

    signal_received = pyqtSignal(str)

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.channels: Dict[str, SignalChannel] = {}
        self._wakeup_notifier: Optional[QSocketNotifier] = None

    def _setup_wakeup_monitoring(self):
        """Setup Qt monitoring of Python's signal wakeup pipe."""
        if SignalRouter._wakeup_pipe_read < 0:
            return  # Pipe not created yet, will be created on first register_signal

        self._wakeup_notifier = QSocketNotifier(
            SignalRouter._wakeup_pipe_read,
            QSocketNotifier.Type.Read,
            self
        )
        self._wakeup_notifier.activated.connect(self._handle_wakeup)
        print(f"Monitoring wakeup pipe fd {SignalRouter._wakeup_pipe_read}", file=sys.stderr)

    def _handle_wakeup(self):
        """Handle wakeup notification - drain pipe to allow more signals."""
        try:
            os.read(SignalRouter._wakeup_pipe_read, 1024)
        except (BlockingIOError, OSError):
            pass

    def register_signal(self, signal_number: int, channel_name: str) -> bool:
        """
        Register a POSIX signal with a descriptive channel name.

        Args:
            signal_number: POSIX signal number (e.g., signal.SIGHUP)
            channel_name: Descriptive name for this signal channel

        Returns:
            True if registration succeeded, False on error
        """
        if channel_name in self.channels:
            print(f"Channel '{channel_name}' already registered",
                  file=sys.stderr)
            return False

        channel = SignalChannel(signal_number, channel_name)

        if not channel.create_endpoints():
            return False

        channel.qt_notifier = QSocketNotifier(
            channel.read_endpoint.fileno(),
            QSocketNotifier.Type.Read,
            self
        )

        channel.qt_notifier.activated.connect(
            lambda: self._handle_channel_activation(channel_name)
        )

        if not SignalRouter.register_channel(channel):
            channel.cleanup()
            return False

        self.channels[channel_name] = channel
        print(f"Registered signal {signal_number} as channel '{channel_name}'", file=sys.stderr)

        # Setup wakeup monitoring if not already done
        if self._wakeup_notifier is None and SignalRouter._wakeup_pipe_read >= 0:
            self._setup_wakeup_monitoring()

        return True

    def _handle_channel_activation(self, channel_name: str):
        """
        Handle Qt notification that a channel has been activated.

        Args:
            channel_name: Name of the activated channel
        """
        print(f"Channel activated: {channel_name}", file=sys.stderr)
        channel = self.channels.get(channel_name)
        if not channel:
            print(f"Channel {channel_name} not found!", file=sys.stderr)
            return

        channel.qt_notifier.setEnabled(False)
        channel.drain()
        print(f"Emitting signal_received for {channel_name}", file=sys.stderr)
        self.signal_received.emit(channel_name)
        channel.qt_notifier.setEnabled(True)

    def cleanup(self):
        """Release all channel resources."""
        for channel in self.channels.values():
            if channel.qt_notifier:
                channel.qt_notifier.setEnabled(False)
            channel.cleanup()
        self.channels.clear()
