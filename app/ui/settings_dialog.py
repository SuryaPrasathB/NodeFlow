"""
Provides a dialog for managing application-wide settings.

This module contains the SettingsDialog class, which allows users to configure
and persist application settings like the default OPC-UA server URL and the
UI theme using Qt's QSettings.
"""
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QLineEdit,
                             QDialogButtonBox, QComboBox, QLabel, QCheckBox)
from PyQt6.QtCore import QSettings

class SettingsDialog(QDialog):
    """
    A dialog for managing application settings.

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
        self.setMinimumWidth(400)

        self.settings = QSettings("MyCompany", "OPCUA-Client")

        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        self.server_url_input = QLineEdit()
        form_layout.addRow(QLabel("Default Server URL:"), self.server_url_input)

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Dark", "Light"])
        form_layout.addRow(QLabel("Theme:"), self.theme_combo)

        self.switch_to_sequencer_checkbox = QCheckBox("Switch to Sequencer tab on run")
        form_layout.addRow(self.switch_to_sequencer_checkbox)

        layout.addLayout(form_layout)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.save_settings)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self.load_settings()

    def load_settings(self):
        """
        Loads settings from persistent storage and populates the dialog fields.

        It retrieves the last saved values for server URL, theme, and other
        options, using sensible defaults if no settings have been saved yet.
        """
        server_url = self.settings.value("server_url", "opc.tcp://localhost:4840/freeopcua/server/")
        theme = self.settings.value("theme", "Dark")
        switch_on_run = self.settings.value("switch_on_run", True, type=bool)

        self.server_url_input.setText(server_url)
        self.theme_combo.setCurrentText(theme)
        self.switch_to_sequencer_checkbox.setChecked(switch_on_run)

    def save_settings(self):
        """
        Saves the current settings from the dialog to persistent storage.

        This method is called when the user clicks 'OK'. It takes the values
        from the input fields and saves them using QSettings, then accepts
        the dialog.
        """
        self.settings.setValue("server_url", self.server_url_input.text())
        self.settings.setValue("theme", self.theme_combo.currentText())
        self.settings.setValue("switch_on_run", self.switch_to_sequencer_checkbox.isChecked())
        self.accept()
