"""
A QListWidget for Displaying and Interacting with Created Sequences.

This module provides the SequenceTreeView, which acts as a library of all
sequences in the current project. It allows users to right-click a sequence
to add a trigger button for it to the dashboard.
"""
import logging
from PyQt6.QtWidgets import QListWidget, QListWidgetItem, QMenu
from PyQt6.QtCore import Qt, pyqtSignal

class SequenceTreeView(QListWidget):
    """
    A QListWidget that displays the available sequences.
    Users can add a sequence to the dashboard as a button via a context menu.
    """
    ## SEQUENCER ENHANCEMENT ##
    # Signal emitted when the user requests to create a widget for a sequence.
    # The payload will be the name of the sequence.
    create_sequence_widget_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.open_context_menu)

    def update_sequences(self, sequence_names):
        """
        Clears the current list and repopulates it with the given sequence names.
        """
        self.clear()
        self.addItems(sequence_names)

    def open_context_menu(self, position):
        """
        Shows a context menu for the selected sequence item.
        """
        item = self.itemAt(position)
        if not item:
            return

        sequence_name = item.text()
        
        context_menu = QMenu(self)
        add_button_action = context_menu.addAction("Add to Dashboard as Button")
        
        # The lambda captures the current sequence_name for the signal payload
        action = context_menu.exec(self.mapToGlobal(position))
        
        if action == add_button_action:
            self.create_sequence_widget_requested.emit(sequence_name)
            logging.info(f"Requested to create a widget for sequence: '{sequence_name}'")