"""
Provides a dialog for searching for nodes across all sequences in a project.

This module contains the GlobalFindDialog class, which allows users to search
for nodes by their labels throughout the entire project.
"""
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLineEdit,
                             QPushButton, QListWidget, QListWidgetItem, QLabel, QWidget)
from PyQt6.QtCore import pyqtSignal, Qt

class GlobalFindDialog(QDialog):
    """
    A dialog to display search results for nodes across the entire project.

    This dialog provides a search input field and a list to display matching
    nodes. When a result is selected, it emits a signal containing the
    sequence name and node UUID, allowing the main application to focus on
    the selected node.

    Attributes:
        result_selected (pyqtSignal): A signal emitted when a search result is
                                      selected. It passes the sequence name (str)
                                      and the node UUID (str).
    """
    result_selected = pyqtSignal(str, str)

    def __init__(self, sequences_data, parent=None):
        """
        Initializes the GlobalFindDialog.

        Args:
            sequences_data (dict): A dictionary containing all the sequence
                                   data for the current project. The keys are
                                   sequence names, and the values are the
                                   sequence data dictionaries.
            parent (QWidget, optional): The parent widget. Defaults to None.
        """
        super().__init__(parent)
        self.sequences_data = sequences_data
        self.setWindowTitle("Find in Project")
        self.setMinimumSize(500, 400)

        layout = QVBoxLayout(self)

        # --- Search Input ---
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Enter node label to search for...")
        self.search_input.returnPressed.connect(self.perform_search)
        search_button = QPushButton("Find")
        search_button.clicked.connect(self.perform_search)
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(search_button)

        # --- Results List ---
        self.results_list = QListWidget()
        self.results_list.itemDoubleClicked.connect(self.on_result_selected)

        layout.addLayout(search_layout)
        layout.addWidget(self.results_list)

    def perform_search(self):
        """
        Iterates through all sequences and nodes to find and display matches.

        The search is case-insensitive and matches against the node's label.
        Results are displayed in a list with the node's label and the sequence
        it belongs to.
        """
        self.results_list.clear()
        search_term = self.search_input.text().lower()
        if not search_term:
            return

        for seq_name, seq_data in self.sequences_data.items():
            for node_data in seq_data.get('nodes', []):
                node_label = node_data.get('config', {}).get('label', '').lower()
                if search_term in node_label:
                    # Create a custom widget for the result item
                    item_widget = QWidget()
                    item_layout = QVBoxLayout(item_widget)
                    item_layout.setContentsMargins(5, 5, 5, 5)

                    label = QLabel(node_data['config']['label'])
                    label.setStyleSheet("font-size: 11pt;")

                    location = QLabel(f"In Sequence: {seq_name}")
                    location.setStyleSheet("font-size: 9pt; color: #888;")

                    item_layout.addWidget(label)
                    item_layout.addWidget(location)

                    list_item = QListWidgetItem(self.results_list)
                    list_item.setSizeHint(item_widget.sizeHint())
                    list_item.setData(Qt.ItemDataRole.UserRole, (seq_name, node_data['uuid']))

                    self.results_list.addItem(list_item)
                    self.results_list.setItemWidget(list_item, item_widget)

    def on_result_selected(self, item):
        """
        Handles the selection of a result from the list.

        Emits the `result_selected` signal with the data of the selected
        result and then closes the dialog.

        Args:
            item (QListWidgetItem): The list widget item that was double-clicked.
        """
        data = item.data(Qt.ItemDataRole.UserRole)
        if data:
            self.result_selected.emit(data[0], data[1])
            self.accept()