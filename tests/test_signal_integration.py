#!/usr/bin/env python
"""Test POSIX signal integration with Qt event loop."""
import sys
import os
import signal
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
from ui import PosixSignalBridge


def test_signal_delivery():
    """Test that POSIX signals are delivered through bridge."""
    app = QApplication.instance() or QApplication(sys.argv)
    bridge = PosixSignalBridge()

    received_signals = []

    def on_signal(channel_name):
        received_signals.append(channel_name)
        print(f"Received signal: {channel_name}")
        app.quit()

    bridge.signal_received.connect(on_signal)
    bridge.register_signal(signal.SIGUSR1, "test_signal")

    # Send signal to self after short delay
    def send_signal():
        print(f"Sending SIGUSR1 to PID {os.getpid()}")
        os.kill(os.getpid(), signal.SIGUSR1)

    QTimer.singleShot(100, send_signal)

    # Timeout after 2 seconds
    QTimer.singleShot(2000, lambda: (print("TIMEOUT"), app.quit()))

    print("Starting Qt event loop...")
    app.exec()

    bridge.cleanup()

    if "test_signal" in received_signals:
        print("✓ Signal delivered successfully")
    else:
        print("✗ Signal NOT delivered")
        print(f"Received: {received_signals}")
        assert False, "Signal was not delivered"


if __name__ == "__main__":
    test_signal_delivery()
    sys.exit(0)
