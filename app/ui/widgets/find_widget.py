"""
A non-modal find widget for the Sequencer Editor, similar to those in IDEs.
"""
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLineEdit, QPushButton, QLabel
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QIcon
from app.utils.paths import resource_path

class FindWidget(QWidget):
    """
    A small overlay widget for searching within a parent view, like a text editor or scene.

    It provides a text input field, next/previous buttons, and a close button.
    It communicates with the parent view via signals.

    Attributes:
        find_next (pyqtSignal): Emitted when the user wants to find the next occurrence.
        find_previous (pyqtSignal): Emitted when the user wants to find the previous occurrence.
        closed (pyqtSignal): Emitted when the widget is closed by the user.
    """
    find_next = pyqtSignal(str)
    find_previous = pyqtSignal(str)
    closed = pyqtSignal()

    def __init__(self, parent=None):
        """
        Initializes the FindWidget.

        Args:
            parent (QWidget, optional): The parent widget. Defaults to None.
        """
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Find")
        self.search_input.returnPressed.connect(self.on_find_next)

        self.prev_button = QPushButton()
        self.prev_button.setIcon(QIcon(resource_path("app/resources/icons/left_arrow.png")))
        self.prev_button.setToolTip("Previous")
        self.next_button = QPushButton()
        self.next_button.setIcon(QIcon(resource_path("app/resources/icons/right_arrow.png")))
        self.next_button.setToolTip("Next")
        self.close_button = QPushButton()
        self.close_button.setIcon(QIcon(resource_path("app/resources/icons/close.png")))
        self.close_button.setToolTip("Close")

        for btn in [self.prev_button, self.next_button, self.close_button]:
            btn.setFixedSize(24, 24)

        layout.addWidget(self.search_input)
        layout.addWidget(self.prev_button)
        layout.addWidget(self.next_button)
        layout.addWidget(self.close_button)

        self.prev_button.clicked.connect(self.on_find_previous)
        self.next_button.clicked.connect(self.on_find_next)
        self.close_button.clicked.connect(self.hide_and_emit)
        
        self.setStyleSheet("""
            QWidget { background-color: #2c2f33; border: 1px solid #555; }
            QLineEdit { border: 1px solid #555; }
            QPushButton { border: none; }
            QPushButton:hover { background-color: #4a4e52; }
        """)

    def on_find_next(self):
        """
        Slot for the 'Next' button or Return key press.

        Emits the `find_next` signal with the current text from the search input.
        """
        text = self.search_input.text()
        if text:
            self.find_next.emit(text)

    def on_find_previous(self):
        """
        Slot for the 'Previous' button.

        Emits the `find_previous` signal with the current text from the search input.
        """
        text = self.search_input.text()
        if text:
            self.find_previous.emit(text)
            
    def show_and_focus(self, pos=None):
        """
        Shows the widget and sets focus to the search input.

        Args:
            pos (tuple, optional): A tuple (x, y) to position the widget. Defaults to None.
        """
        self.show()
        if pos is not None:
            self.move(*pos)
        # Use QTimer.singleShot to ensure focus is set after the show event is processed.
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(0, self._focus_input)

    def _focus_input(self):
        """Internal helper to set focus and select all text in the input field."""
        self.search_input.setFocus()
        self.search_input.selectAll()
        
    def hide_and_emit(self):
        """Hides the widget and emits the 'closed' signal."""
        self.hide()
        self.closed.emit()

    def keyPressEvent(self, event):
        """
        Handles key presses, specifically listening for the Escape key to close the widget.

        Args:
            event (QKeyEvent): The key press event.
        """
        if event.key() == Qt.Key.Key_Escape:
            self.hide_and_emit()
        else:
            super().keyPressEvent(event)
