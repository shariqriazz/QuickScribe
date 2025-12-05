"""
System tray UI component for QuickScribe.

Provides visual feedback of application state through system tray icon
and quick access to controls via context menu.
"""

from enum import Enum
from typing import Optional
from PyQt6.QtWidgets import QSystemTrayIcon, QMenu
from PyQt6.QtGui import QIcon, QAction
from PyQt6.QtCore import QObject, pyqtSignal


class AppState(Enum):
    """Application states reflected in system tray."""
    IDLE = "idle"
    RECORDING = "recording"
    PROCESSING = "processing"
    ERROR = "error"


class SystemTrayUI(QObject):
    """
    System tray icon that reflects application state.

    Signals:
        start_recording_requested: User clicked start recording
        stop_recording_requested: User clicked stop recording
        quit_requested: User clicked quit
    """

    start_recording_requested = pyqtSignal()
    stop_recording_requested = pyqtSignal()
    quit_requested = pyqtSignal()

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)

        self._current_state = AppState.IDLE
        self._tray_icon = QSystemTrayIcon(self)
        self._menu = QMenu()

        self._setup_menu()
        self._setup_tray()

    def _setup_menu(self):
        """Create context menu for tray icon."""
        self._action_start = QAction("Start Recording", self)
        self._action_start.triggered.connect(self.start_recording_requested.emit)
        self._menu.addAction(self._action_start)

        self._action_stop = QAction("Stop Recording", self)
        self._action_stop.triggered.connect(self.stop_recording_requested.emit)
        self._action_stop.setEnabled(False)
        self._menu.addAction(self._action_stop)

        self._menu.addSeparator()

        self._action_quit = QAction("Quit", self)
        self._action_quit.triggered.connect(self.quit_requested.emit)
        self._menu.addAction(self._action_quit)

    def _setup_tray(self):
        """Initialize tray icon."""
        self._tray_icon.setContextMenu(self._menu)
        self._update_icon()
        self._tray_icon.show()

    def _update_icon(self):
        """Update icon based on current state."""
        import os

        # Get icon directory path relative to this file
        icon_dir = os.path.join(os.path.dirname(__file__), 'icons')

        if self._current_state == AppState.RECORDING:
            icon_path = os.path.join(icon_dir, 'recording.svg')
            tooltip = "QuickScribe - Recording"
        elif self._current_state == AppState.PROCESSING:
            icon_path = os.path.join(icon_dir, 'processing.svg')
            tooltip = "QuickScribe - Processing"
        elif self._current_state == AppState.ERROR:
            icon_path = os.path.join(icon_dir, 'error.svg')
            tooltip = "QuickScribe - Error"
        else:  # IDLE
            icon_path = os.path.join(icon_dir, 'idle.svg')
            tooltip = "QuickScribe - Idle"

        icon = QIcon(icon_path)
        self._tray_icon.setIcon(icon)
        self._tray_icon.setToolTip(tooltip)

    def set_state(self, state: AppState):
        """
        Update tray icon to reflect new application state.

        Args:
            state: New application state
        """
        self._current_state = state
        self._update_icon()

        # Update menu actions based on state
        if state == AppState.RECORDING:
            self._action_start.setEnabled(False)
            self._action_stop.setEnabled(True)
        else:
            self._action_start.setEnabled(True)
            self._action_stop.setEnabled(False)

    def show_message(self, title: str, message: str):
        """
        Show notification message from tray icon.

        Args:
            title: Notification title
            message: Notification message
        """
        self._tray_icon.showMessage(title, message)

    def show_error(self, error_message: str):
        """
        Display error state and show toast notification.

        Args:
            error_message: Error message to display in toast
        """
        self.set_state(AppState.ERROR)
        self._tray_icon.showMessage("Dictation API error", error_message, QSystemTrayIcon.MessageIcon.Critical, 3000)

    def cleanup(self):
        """Clean up tray icon resources."""
        self._tray_icon.hide()
