from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QLineEdit, 
                             QDialogButtonBox, QComboBox, QLabel, QCheckBox)
from PyQt6.QtCore import QSettings

class SettingsDialog(QDialog):
    """
    A dialog for managing application settings, such as the OPC-UA server URL
    and the visual theme.
    """
    def __init__(self, parent=None):
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

        ## UX REFINEMENT ##
        # Add the new setting checkbox
        self.switch_to_sequencer_checkbox = QCheckBox("Switch to Sequencer tab on run")
        form_layout.addRow(self.switch_to_sequencer_checkbox)

        layout.addLayout(form_layout)
        
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.save_settings)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self.load_settings()

    def load_settings(self):
        """Loads settings from persistent storage and populates the dialog."""
        server_url = self.settings.value("server_url", "opc.tcp://localhost:4840/freeopcua/server/")
        theme = self.settings.value("theme", "Dark")
        # Load the new setting, defaulting to True (the old behavior)
        switch_on_run = self.settings.value("switch_on_run", True, type=bool)
        
        self.server_url_input.setText(server_url)
        self.theme_combo.setCurrentText(theme)
        self.switch_to_sequencer_checkbox.setChecked(switch_on_run)

    def save_settings(self):
        """Saves the current settings from the dialog to persistent storage."""
        self.settings.setValue("server_url", self.server_url_input.text())
        self.settings.setValue("theme", self.theme_combo.currentText())
        self.settings.setValue("switch_on_run", self.switch_to_sequencer_checkbox.isChecked())
        self.accept()
