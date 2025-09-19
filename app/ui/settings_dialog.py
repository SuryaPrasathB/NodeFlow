"""
Provides a dialog for managing application-wide settings.

This module contains the SettingsDialog class, which allows users to configure
and persist application settings like the default OPC-UA server URL, UI theme,
and MySQL database credentials using Qt's QSettings.
"""
import logging
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QLineEdit,
                             QDialogButtonBox, QComboBox, QLabel, QCheckBox,
                             QTabWidget, QWidget, QPushButton, QMessageBox)
from PyQt6.QtCore import QSettings

from app.core.mysql_manager import MySQLManager

class SettingsDialog(QDialog):
    """
    A dialog for managing application settings, organized into tabs.

    This dialog provides a user interface for viewing and modifying settings
    that are persisted between application sessions. It handles loading the
    current settings into the UI controls and saving the new values back to
    persistent storage.
    """
    def __init__(self, parent=None):
        """
        Initializes the SettingsDialog.

        Args:
            parent (QWidget, optional): The parent widget. Defaults to None.
        """
        super().__init__(parent)
        self.setWindowTitle("Application Settings")
        self.setMinimumWidth(450)

        self.settings = QSettings("MyCompany", "NodeFlow")

        layout = QVBoxLayout(self)

        # Create tab widget
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)

        # General Settings Tab
        self.general_tab = QWidget()
        self.setup_general_tab()
        self.tab_widget.addTab(self.general_tab, "General")

        # MySQL Settings Tab
        self.mysql_tab = QWidget()
        self.setup_mysql_tab()
        self.tab_widget.addTab(self.mysql_tab, "MySQL")

        # Dialog buttons
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.save_settings)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self.load_settings()

    def setup_general_tab(self):
        """
        Sets up the UI for the 'General' settings tab.
        """
        layout = QFormLayout(self.general_tab)

        self.server_url_input = QLineEdit()
        layout.addRow(QLabel("Default OPC-UA Server URL:"), self.server_url_input)

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Dark", "Light"])
        layout.addRow(QLabel("Theme:"), self.theme_combo)

        self.switch_to_sequencer_checkbox = QCheckBox("Switch to Sequencer tab on run")
        layout.addRow(self.switch_to_sequencer_checkbox)

    def setup_mysql_tab(self):
        """
        Sets up the UI for the 'MySQL' settings tab.
        """
        layout = QFormLayout(self.mysql_tab)

        self.mysql_host_input = QLineEdit()
        self.mysql_user_input = QLineEdit()
        self.mysql_password_input = QLineEdit()
        self.mysql_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.mysql_db_input = QLineEdit()

        layout.addRow(QLabel("Host:"), self.mysql_host_input)
        layout.addRow(QLabel("Username:"), self.mysql_user_input)
        layout.addRow(QLabel("Password:"), self.mysql_password_input)
        layout.addRow(QLabel("Database Name:"), self.mysql_db_input)

        test_button = QPushButton("Test Connection")
        test_button.clicked.connect(self.test_mysql_connection)
        layout.addRow(test_button)

    def test_mysql_connection(self):
        """
        Tests the MySQL connection using the provided credentials.
        """
        try:
            from app.core.mysql_manager import MySQLManager

            logging.info("Attempting to test MySQL connection.")
            host = self.mysql_host_input.text()
            user = self.mysql_user_input.text()
            password = self.mysql_password_input.text()
            database = self.mysql_db_input.text()
            logging.info(f"MySQL connection details - Host: {host}, User: {user}, Database: {database}")

            if not all(val.strip() for val in [host, user, database]):
                logging.warning("MySQL connection test failed: Missing information.")
                QMessageBox.warning(self, "Missing Information", "Please fill in Host, Username, and Database Name. These fields cannot be empty or contain only whitespace.")
                return

            # Use a temporary manager to test connection
            logging.info("Creating MySQLManager instance.")
            manager = MySQLManager(host=host, user=user, password=password, database=database)

            # First, try to create the database. This connects to the server without a db.
            logging.info("Attempting to create database if not exists.")
            success, message = manager.create_database_if_not_exists()
            if not success:
                logging.error(f"Database creation/verification failed: {message}")
                QMessageBox.critical(self, "Connection Failed", f"Could not create or verify database existence.\nError: {message}")
                return
            logging.info("Database creation/verification successful.")

            # Now, try to connect to the specific database
            logging.info("Attempting to connect to the database.")
            success, message = manager.connect()
            if success:
                logging.info("MySQL connection successful.")
                QMessageBox.information(self, "Connection Successful", "Successfully connected to the MySQL database.")
                manager.close()
                logging.info("MySQL connection closed.")
            else:
                logging.error(f"MySQL connection failed: {message}")
                QMessageBox.critical(self, "Connection Failed", f"Failed to connect to the database.\nError: {message}")
        except ImportError:
            logging.error("MySQL connector not found. Please install it with 'pip install mysql-connector-python'")
            QMessageBox.critical(self, "Dependency Error", "The 'mysql-connector-python' library is not installed. Please install it via pip and restart the application.")
        except Exception as e:
            logging.error(f"An unexpected error occurred during MySQL connection test: {e}", exc_info=True)
            QMessageBox.critical(self, "Error", f"An unexpected error occurred: {e}")

    def load_settings(self):
        """
        Loads settings from persistent storage and populates the dialog fields.
        """
        # General settings
        server_url = self.settings.value("server_url", "opc.tcp://localhost:4840/freeopcua/server/")
        theme = self.settings.value("theme", "Dark")
        switch_on_run = self.settings.value("switch_on_run", True, type=bool)

        self.server_url_input.setText(server_url)
        self.theme_combo.setCurrentText(theme)
        self.switch_to_sequencer_checkbox.setChecked(switch_on_run)

        # MySQL settings
        self.mysql_host_input.setText(self.settings.value("mysql/host", "localhost"))
        self.mysql_user_input.setText(self.settings.value("mysql/user", "root"))
        self.mysql_password_input.setText(self.settings.value("mysql/password", ""))
        self.mysql_db_input.setText(self.settings.value("mysql/database", "nodeflow_db"))


    def save_settings(self):
        """
        Saves the current settings from the dialog to persistent storage.
        """
        # General settings
        self.settings.setValue("server_url", self.server_url_input.text())
        self.settings.setValue("theme", self.theme_combo.currentText())
        self.settings.setValue("switch_on_run", self.switch_to_sequencer_checkbox.isChecked())

        # MySQL settings
        self.settings.beginGroup("mysql")
        self.settings.setValue("host", self.mysql_host_input.text())
        self.settings.setValue("user", self.mysql_user_input.text())
        self.settings.setValue("password", self.mysql_password_input.text())
        self.settings.setValue("database", self.mysql_db_input.text())
        self.settings.endGroup()

        self.accept()