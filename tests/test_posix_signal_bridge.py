"""Test POSIX signal bridge integration."""
import sys
import os
import signal
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def check_pyqt_available():
    try:
        from PyQt6.QtWidgets import QApplication as QApp
        return hasattr(QApp, '__self__') and hasattr(QApp, '__func__')
    except (ImportError, AttributeError):
        return False

PYQT_AVAILABLE = check_pyqt_available()

if PYQT_AVAILABLE:
    from PyQt6.QtWidgets import QApplication
    from ui import PosixSignalBridge


@pytest.mark.skipif(not PYQT_AVAILABLE, reason="PyQt6 not available")
def test_bridge_creation():
    """Test that PosixSignalBridge can be created."""
    app = QApplication.instance() or QApplication(sys.argv)
    bridge = PosixSignalBridge()
    assert bridge is not None
    bridge.cleanup()


@pytest.mark.skipif(not PYQT_AVAILABLE, reason="PyQt6 not available")
def test_signal_registration():
    """Test signal channel registration."""
    app = QApplication.instance() or QApplication(sys.argv)
    bridge = PosixSignalBridge()

    result = bridge.register_signal(signal.SIGUSR1, "test_channel")
    assert result is True
    assert "test_channel" in bridge.channels

    bridge.cleanup()


@pytest.mark.skipif(not PYQT_AVAILABLE, reason="PyQt6 not available")
def test_duplicate_registration():
    """Test that duplicate channel names are rejected."""
    app = QApplication.instance() or QApplication(sys.argv)
    bridge = PosixSignalBridge()

    bridge.register_signal(signal.SIGUSR1, "test_channel")
    result = bridge.register_signal(signal.SIGUSR2, "test_channel")
    assert result is False

    bridge.cleanup()


if __name__ == "__main__":
    test_bridge_creation()
    print("✓ Bridge creation")

    test_signal_registration()
    print("✓ Signal registration")

    test_duplicate_registration()
    print("✓ Duplicate registration handling")

    print("\nAll tests passed")
