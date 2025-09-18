"""
Custom Logging Components for the PyQt Application.

This module provides a custom QtLogHandler that can be added to Python's
standard logging system to redirect log messages to a Qt signal. It also
provides the LogWidget, a QPlainTextEdit subclass that displays these
log messages in the UI.
"""
import logging
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTextEdit
from PyQt6.QtGui import QColor, QPalette

class QtLogHandler(logging.Handler, QObject):
    """
    A custom logging handler that emits a signal for each log record.
    Connect this signal to a slot in the GUI to display log messages.
    """
    log_received = pyqtSignal(str, str) # Signal emits log level and message

    def __init__(self):
        super().__init__()
        QObject.__init__(self)

    def emit(self, record):
        """
        Formats and emits the log record as a signal.
        """
        msg = self.format(record)
        self.log_received.emit(record.levelname, msg)

class LogWidget(QWidget):
    """
    A widget that displays log messages received from the QtLogHandler.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setLayout(QVBoxLayout())
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        
        # Set a dark theme for the logger
        palette = self.log_display.palette()
        palette.setColor(QPalette.ColorRole.Base, QColor(30, 31, 34))
        palette.setColor(QPalette.ColorRole.Text, QColor(220, 220, 220))
        self.log_display.setPalette(palette)
        
        self.layout().addWidget(self.log_display)
        self.layout().setContentsMargins(0,0,0,0)

    def add_log_message(self, level, message):
        """
        Appends a formatted log message to the text display.
        """
        color_map = {
            "INFO": "#cccccc", # Light gray
            "WARNING": "orange",
            "ERROR": "#ff5555", # A softer red
            "CRITICAL": "#ff1c1c",
            "DEBUG": "cyan"
        }
        color = color_map.get(level, "#cccccc")
        
        html_message = f'<font color="{color}">{message}</font>'
        self.log_display.append(html_message)
