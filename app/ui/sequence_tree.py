"""
A QListWidget for displaying and interacting with created sequences.

This module provides the SequenceTreeView, which acts as a library of all
sequences in the current project. It allows users to right-click a sequence
to add a trigger button for it to the dashboard.
"""
import logging
from PyQt6.QtWidgets import QListWidget, QMenu
from PyQt6.QtCore import Qt, pyqtSignal

class SequenceTreeView(QListWidget):
    """
    A QListWidget that displays the available sequences in the project.

    This widget shows a list of all created sequences. Users can interact with
    this list, primarily by right-clicking a sequence to open a context menu,
    which allows them to perform actions such as adding a trigger button for
    that sequence to the main dashboard.

    Attributes:
        create_sequence_widget_requested (pyqtSignal): Emitted when the user
            selects the option to create a widget for a sequence. Passes the
            sequence name (str).
    """
    create_sequence_widget_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        """
        Initializes the SequenceTreeView.

        Args:
            parent (QWidget, optional): The parent widget. Defaults to None.
        """
        super().__init__(parent)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.open_context_menu)

    def update_sequences(self, sequence_names):
        """
        Clears the current list and repopulates it with the given sequence names.

        Args:
            sequence_names (list[str]): A list of names of the sequences to display.
        """
        self.clear()
        self.addItems(sequence_names)

    def open_context_menu(self, position):
        """
        Shows a context menu for the selected sequence item.

        The context menu provides actions that can be performed on the selected
        sequence, such as "Add to Dashboard as Button".

        Args:
            position (QPoint): The position where the context menu was requested.
        """
        item = self.itemAt(position)
        if not item:
            return

        sequence_name = item.text()

        context_menu = QMenu(self)
        add_button_action = context_menu.addAction("Add to Dashboard as Button")

        action = context_menu.exec(self.mapToGlobal(position))

        if action == add_button_action:
            self.create_sequence_widget_requested.emit(sequence_name)
            logging.info(f"Requested to create a widget for sequence: '{sequence_name}'")