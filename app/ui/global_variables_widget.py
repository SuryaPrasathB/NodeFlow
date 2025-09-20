"""
Global Variables Widget for the Node-Based Sequencer.

This module contains the GlobalVariablesWidget class, which provides a UI
for users to define and manage global variables for their projects. These
variables can then be accessed and manipulated by nodes within the sequence editor.
"""
import logging
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
                             QPushButton, QHBoxLayout, QComboBox, QHeaderView)
from PyQt6.QtCore import Qt, pyqtSignal

class GlobalVariablesWidget(QWidget):
    """
    A widget for managing global variables.

    This widget displays global variables in a table and allows users to add,
    remove, and edit them. It signals changes so that other parts of the
    application, like node configuration dialogs, can stay in sync.
    """
    variables_changed = pyqtSignal()

    def __init__(self, main_window, parent=None):
        """
        Initializes the GlobalVariablesWidget.

        Args:
            main_window (MainWindow): A reference to the main application window,
                                      which holds the global_variables dictionary.
            parent (QWidget, optional): The parent widget. Defaults to None.
        """
        super().__init__(parent)
        self.main_window = main_window
        self.data_types = ["String", "Integer", "Float", "Boolean"]

        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)

        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Name", "Type", "Value"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.itemChanged.connect(self.on_item_changed)
        layout.addWidget(self.table)

        button_layout = QHBoxLayout()
        add_button = QPushButton("Add Variable")
        add_button.clicked.connect(self.add_variable)
        remove_button = QPushButton("Remove Variable")
        remove_button.clicked.connect(self.remove_variable)
        button_layout.addWidget(add_button)
        button_layout.addWidget(remove_button)
        layout.addLayout(button_layout)

    def add_variable(self):
        """Adds a new, empty row to the variables table."""
        row_position = self.table.rowCount()
        self.table.insertRow(row_position)

        name_item = QTableWidgetItem(f"new_variable_{row_position}")
        self.table.setItem(row_position, 0, name_item)

        type_combo = QComboBox()
        type_combo.addItems(self.data_types)
        type_combo.currentIndexChanged.connect(self.on_type_changed)
        self.table.setCellWidget(row_position, 1, type_combo)

        value_item = QTableWidgetItem("0")
        self.table.setItem(row_position, 2, value_item)

        self.update_global_variables()

    def remove_variable(self):
        """Removes the currently selected row from the variables table."""
        current_row = self.table.currentRow()
        if current_row >= 0:
            self.table.removeRow(current_row)
            self.update_global_variables()

    def on_item_changed(self, item):
        """
        Handles changes to items in the table (Name or Value).

        Args:
            item (QTableWidgetItem): The item that was changed.
        """
        self.update_global_variables()

    def on_type_changed(self, index):
        """
        Handles changes to the data type QComboBox.

        Args:
            index (int): The new index of the combo box.
        """
        self.update_global_variables()

    def update_global_variables(self):
        """
        Reads the entire table and updates the main window's global_variables
        dictionary. Emits the variables_changed signal.
        """
        variables = {}
        for row in range(self.table.rowCount()):
            try:
                name = self.table.item(row, 0).text()
                type_widget = self.table.cellWidget(row, 1)
                type_str = type_widget.currentText() if type_widget else "String"
                value_str = self.table.item(row, 2).text()

                value = self.cast_value(value_str, type_str)
                variables[name] = {'type': type_str, 'value': value}
            except Exception as e:
                logging.error(f"Error processing global variable at row {row}: {e}")

        self.main_window.global_variables = variables
        self.variables_changed.emit()
        logging.debug(f"Global variables updated: {self.main_window.global_variables}")

    def cast_value(self, value_str, type_str):
        """
        Casts a string value to the specified data type.

        Args:
            value_str (str): The string representation of the value.
            type_str (str): The target data type.

        Returns:
            The value cast to the appropriate type.
        """
        try:
            if type_str == "Integer":
                return int(value_str)
            elif type_str == "Float":
                return float(value_str)
            elif type_str == "Boolean":
                return value_str.lower() in ['true', '1', 't', 'yes']
            else: # String
                return value_str
        except (ValueError, TypeError):
            logging.warning(f"Could not cast '{value_str}' to {type_str}. Returning as string.")
            return value_str

    def load_variables(self):
        """
        Populates the table from the main window's global_variables dictionary.
        """
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        for name, data in self.main_window.global_variables.items():
            row_position = self.table.rowCount()
            self.table.insertRow(row_position)

            name_item = QTableWidgetItem(name)
            self.table.setItem(row_position, 0, name_item)

            type_combo = QComboBox()
            type_combo.addItems(self.data_types)
            type_combo.setCurrentText(data.get('type', 'String'))
            type_combo.currentIndexChanged.connect(self.on_type_changed)
            self.table.setCellWidget(row_position, 1, type_combo)

            value_item = QTableWidgetItem(str(data.get('value', '')))
            self.table.setItem(row_position, 2, value_item)
        self.table.blockSignals(False)
