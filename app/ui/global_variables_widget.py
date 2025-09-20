"""
Global Variables Widget for the Node-Based Sequencer.

This module contains the GlobalVariablesWidget class, which provides a UI
for users to define and manage global variables for their projects. These
variables can then be accessed and manipulated by nodes within the sequence editor.
"""
import logging
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
                             QPushButton, QHBoxLayout, QComboBox, QHeaderView, QCheckBox)
from PyQt6.QtCore import Qt, pyqtSignal

class GlobalVariablesWidget(QWidget):
    """
    A widget for managing global variables.
    This widget displays global variables in a table and allows users to add,
    remove, and edit their definitions (name, type, initial value, retentive status).
    It also displays the live 'current value' during sequence execution.
    """
    variables_changed = pyqtSignal()

    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.data_types = ["String", "Integer", "Float", "Boolean"]

        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Name", "Type", "Initial Value", "Retentive", "Current Value"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
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
        """Adds a new, empty row to the variables table for definition."""
        row_position = self.table.rowCount()
        self.table.insertRow(row_position)

        name_item = QTableWidgetItem(f"new_variable_{row_position}")
        self.table.setItem(row_position, 0, name_item)

        type_combo = QComboBox()
        type_combo.addItems(self.data_types)
        type_combo.currentIndexChanged.connect(self.on_cell_widget_changed)
        self.table.setCellWidget(row_position, 1, type_combo)

        initial_value_item = QTableWidgetItem("0")
        self.table.setItem(row_position, 2, initial_value_item)

        retentive_checkbox = QCheckBox()
        retentive_checkbox.stateChanged.connect(self.on_cell_widget_changed)
        cell_widget = QWidget()
        layout = QHBoxLayout(cell_widget)
        layout.addWidget(retentive_checkbox)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setContentsMargins(0,0,0,0)
        self.table.setCellWidget(row_position, 3, cell_widget)

        current_value_item = QTableWidgetItem("0")
        current_value_item.setFlags(current_value_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.table.setItem(row_position, 4, current_value_item)

        self.update_global_variables()

    def remove_variable(self):
        """Removes the currently selected row from the variables table."""
        current_row = self.table.currentRow()
        if current_row >= 0:
            self.table.removeRow(current_row)
            self.update_global_variables()

    def on_item_changed(self, item):
        """Handles changes to editable items in the table (Name or Initial Value)."""
        self.update_global_variables()

    def on_cell_widget_changed(self, index):
        """Handles changes to cell widgets (Type ComboBox or Retentive CheckBox)."""
        self.update_global_variables()

    def update_global_variables(self):
        """
        Reads the entire table and updates the main window's global_variables
        dictionary. Emits the variables_changed signal. This method defines the
        structure of the variables but preserves the 'current_value' from the
        existing state if available.
        """
        variables = {}
        for row in range(self.table.rowCount()):
            try:
                name = self.table.item(row, 0).text()
                if not name: continue

                type_widget = self.table.cellWidget(row, 1)
                type_str = type_widget.currentText() if type_widget else "String"

                initial_value_str = self.table.item(row, 2).text()
                initial_value = self.cast_value(initial_value_str, type_str)

                retentive_widget = self.table.cellWidget(row, 3)
                retentive = retentive_widget.findChild(QCheckBox).isChecked() if retentive_widget else False

                # Preserve the existing current_value if the variable already exists.
                # Otherwise, the current_value starts as the initial_value.
                current_value = initial_value
                if name in self.main_window.global_variables:
                    current_value = self.main_window.global_variables[name].get('current_value', initial_value)

                variables[name] = {
                    'type': type_str,
                    'initial_value': initial_value,
                    'retentive': retentive,
                    'current_value': current_value
                }

                # Update the read-only current value display in the table
                current_val_item = self.table.item(row, 4)
                if current_val_item.text() != str(current_value):
                    current_val_item.setText(str(current_value))

            except Exception as e:
                logging.error(f"Error processing global variable at row {row}: {e}")

        self.main_window.global_variables = variables
        self.variables_changed.emit()
        logging.debug(f"Global variables updated: {self.main_window.global_variables}")

    def cast_value(self, value_str, type_str):
        """Casts a string value to the specified data type."""
        try:
            if type_str == "Integer":
                return int(float(value_str)) # Handle "1.0"
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
        """Populates the table from the main window's global_variables dictionary."""
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        for name, data in self.main_window.global_variables.items():
            row_position = self.table.rowCount()
            self.table.insertRow(row_position)

            self.table.setItem(row_position, 0, QTableWidgetItem(name))

            type_combo = QComboBox()
            type_combo.addItems(self.data_types)
            type_combo.setCurrentText(data.get('type', 'String'))
            type_combo.currentIndexChanged.connect(self.on_cell_widget_changed)
            self.table.setCellWidget(row_position, 1, type_combo)

            self.table.setItem(row_position, 2, QTableWidgetItem(str(data.get('initial_value', ''))))

            retentive_checkbox = QCheckBox()
            retentive_checkbox.setChecked(data.get('retentive', False))
            retentive_checkbox.stateChanged.connect(self.on_cell_widget_changed)
            cell_widget = QWidget()
            layout = QHBoxLayout(cell_widget)
            layout.addWidget(retentive_checkbox)
            layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.setContentsMargins(0,0,0,0)
            self.table.setCellWidget(row_position, 3, cell_widget)

            current_value_item = QTableWidgetItem(str(data.get('current_value', '')))
            current_value_item.setFlags(current_value_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row_position, 4, current_value_item)

        self.table.blockSignals(False)

    def update_variable_display(self, name, value):
        """Updates a single variable's 'Current Value' cell in the table."""
        for row in range(self.table.rowCount()):
            if self.table.item(row, 0).text() == name:
                # Block signals to prevent this UI update from re-triggering a full update
                self.table.blockSignals(True)
                self.table.item(row, 4).setText(str(value))
                self.table.blockSignals(False)
                break
