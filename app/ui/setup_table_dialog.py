"""
Dialog for setting up a MySQL table, allowing users to add new columns.
"""
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QLineEdit,
                             QDialogButtonBox, QComboBox, QLabel, QPushButton,
                             QMessageBox, QListView, QHBoxLayout)
from PyQt6.QtCore import QStringListModel
from app.core.mysql_manager import MySQLManager

class SetupTableDialog(QDialog):
    """
    A dialog to manage a specific MySQL table's schema, primarily for adding columns.
    """
    def __init__(self, parent, host, user, password, database):
        super().__init__(parent)
        self.setWindowTitle("Set up Database Table")
        self.setMinimumWidth(400)

        self.manager = MySQLManager(host, user, password, database)
        
        # --- UI Elements ---
        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        self.table_combo = QComboBox()
        self.column_list_view = QListView()
        self.column_list_model = QStringListModel()
        self.column_list_view.setModel(self.column_list_model)

        self.new_column_name_input = QLineEdit()
        self.new_column_type_combo = QComboBox()
        self.new_column_type_combo.addItems([
            "VARCHAR(255)", "TEXT", "INT", "FLOAT", "DOUBLE", "BOOLEAN", "DATE", "DATETIME", "TIMESTAMP"
        ])
        
        self.add_column_button = QPushButton("Add Column")

        form_layout.addRow(QLabel("Select Table:"), self.table_combo)
        form_layout.addRow(QLabel("Existing Columns:"), self.column_list_view)
        
        add_column_layout = QHBoxLayout()
        add_column_layout.addWidget(self.new_column_name_input)
        add_column_layout.addWidget(self.new_column_type_combo)
        add_column_layout.addWidget(self.add_column_button)
        
        form_layout.addRow(QLabel("New Column:"), add_column_layout)

        layout.addLayout(form_layout)

        # --- Connections ---
        self.table_combo.currentIndexChanged.connect(self.refresh_columns)
        self.add_column_button.clicked.connect(self.add_column)

        # --- Initial Population ---
        self.refresh_tables()

    def refresh_tables(self):
        """Fetches and populates the list of tables."""
        success, msg = self.manager.connect()
        if not success:
            QMessageBox.critical(self, "Connection Failed", f"Could not connect to database.\n{msg}")
            return

        tables = self.manager.get_all_tables()
        self.manager.close()

        if isinstance(tables, list):
            self.table_combo.clear()
            self.table_combo.addItems(tables)
        else:
            QMessageBox.warning(self, "Error", f"Could not fetch tables: {tables}")

    def refresh_columns(self):
        """Fetches and displays the columns for the currently selected table."""
        table_name = self.table_combo.currentText()
        if not table_name:
            self.column_list_model.setStringList([])
            return

        success, msg = self.manager.connect()
        if not success:
            QMessageBox.critical(self, "Connection Failed", f"Could not connect to database.\n{msg}")
            return

        columns = self.manager.get_table_columns(table_name)
        self.manager.close()

        if isinstance(columns, list):
            self.column_list_model.setStringList(columns)
        else:
            self.column_list_model.setStringList([])
            # Optionally show an error, but it might be noisy if the table doesn't exist yet.
            # QMessageBox.warning(self, "Error", f"Could not fetch columns: {columns}")

    def add_column(self):
        """Adds the new column to the selected table."""
        table_name = self.table_combo.currentText()
        column_name = self.new_column_name_input.text().strip()
        column_type = self.new_column_type_combo.currentText()

        if not all([table_name, column_name, column_type]):
            QMessageBox.warning(self, "Missing Information", "Please select a table and provide a name and type for the new column.")
            return

        success, msg = self.manager.connect()
        if not success:
            QMessageBox.critical(self, "Connection Failed", f"Could not connect to database.\n{msg}")
            return

        add_success, add_msg = self.manager.add_column_to_table(table_name, column_name, column_type)
        self.manager.close()

        if add_success:
            QMessageBox.information(self, "Success", f"Column '{column_name}' added to table '{table_name}'.")
            self.new_column_name_input.clear()
            self.refresh_columns() # Refresh the list to show the new column
        else:
            QMessageBox.critical(self, "Error", f"Failed to add column: {add_msg}")
