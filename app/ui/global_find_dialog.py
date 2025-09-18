"""
A dialog for searching for nodes across all sequences in a project.
"""
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, 
                             QPushButton, QListWidget, QListWidgetItem, QLabel, QWidget)
from PyQt6.QtCore import pyqtSignal, Qt

class GlobalFindDialog(QDialog):
    """
    A dialog to display search results from across the entire project.
    """
    result_selected = pyqtSignal(str, str) # Emits sequence_name, node_uuid

    def __init__(self, sequences_data, parent=None):
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
        """Iterates through all sequences and nodes to find matches."""
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
        """Emits the data of the selected result and closes the dialog."""
        data = item.data(Qt.ItemDataRole.UserRole)
        if data:
            self.result_selected.emit(data[0], data[1])
            self.accept()