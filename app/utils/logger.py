"""
Custom Logging Components for the PyQt Application.

This module provides a custom QtLogHandler that can be added to Python's
standard logging system to redirect log messages to a Qt signal. It also
provides the LogWidget, a QPlainTextEdit subclass that displays these
log messages in the UI, complete with color-coding for different log levels.
"""
import logging
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTextEdit
from PyQt6.QtGui import QColor, QPalette

class QtLogHandler(logging.Handler, QObject):
    """
    A custom logging handler that redirects Python's logging output to a Qt signal.

    This handler is designed to be integrated into a PyQt application, allowing
    log messages to be displayed in the GUI in real-time. It captures log records,
    formats them, and emits a signal containing the log level and the formatted message.

    Attributes:
        log_received (pyqtSignal): A signal that emits the log level (str) and
                                   the log message (str) for each record.
    """
    log_received = pyqtSignal(str, str)

    def __init__(self):
        """Initializes the QtLogHandler."""
        super().__init__()
        QObject.__init__(self)

    def emit(self, record):
        """
        Formats and emits the log record via the log_received signal.

        This method is called by the logging framework for each log record.

        Args:
            record (logging.LogRecord): The log record to be processed.
        """
        msg = self.format(record)
        self.log_received.emit(record.levelname, msg)

class LogWidget(QWidget):
    """
    A QWidget for displaying log messages from the QtLogHandler.

    This widget contains a QTextEdit that is styled and configured to display
    log messages. It provides a slot (`add_log_message`) to receive log data,
    which it then formats with appropriate colors based on the log level
    and appends to the display.

    Args:
        parent (QWidget, optional): The parent widget. Defaults to None.
    """
    def __init__(self, parent=None):
        """
        Initializes the LogWidget.

        Args:
            parent (QWidget, optional): The parent widget. Defaults to None.
        """
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
        Appends a color-coded log message to the text display.

        The color of the message is determined by the log level.

        Args:
            level (str): The log level (e.g., "INFO", "WARNING", "ERROR").
            message (str): The log message to be displayed.
        """
        color_map = {
            "INFO": "#cccccc",      # Light gray
            "WARNING": "orange",
            "ERROR": "#ff5555",      # A softer red
            "CRITICAL": "#ff1c1c",
            "DEBUG": "cyan"
        }
        color = color_map.get(level, "#cccccc")

        html_message = f'<font color="{color}">{message}</font>'
        self.log_display.append(html_message)
