"""
Configuration Dialog for Sequencer Nodes.

This module provides the dialog windows used to configure the properties of
different nodes in the sequencer, such as method arguments.
"""
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QLineEdit, 
                             QDialogButtonBox, QCheckBox, QLabel)

class NodeConfigDialog(QDialog):
    """
    A dialog to configure a Method Call node in the sequencer, now with an
    option to use a value from a data connection as an argument.
    """
    def __init__(self, parent=None, current_config=None):
        super().__init__(parent)
        self.setWindowTitle("Configure Method Node")
        self.config = current_config or {}

        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        self.method_label = QLabel(f"<b>{self.config.get('label', 'N/A')}</b>")
        form_layout.addRow("Method:", self.method_label)

        self.has_argument_checkbox = QCheckBox("Pass Input Argument")
        form_layout.addRow(self.has_argument_checkbox)

        # Checkbox to switch between static value and connected value
        self.use_connected_input_checkbox = QCheckBox("Use Value from Data Connection")
        form_layout.addRow(self.use_connected_input_checkbox)

        self.argument_input = QLineEdit()
        self.argument_input.setPlaceholderText("Enter static value to pass to the method")
        form_layout.addRow("Static Argument Value:", self.argument_input)
        
        layout.addLayout(form_layout)
        
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        # Connect signals to update UI state
        self.has_argument_checkbox.toggled.connect(self.update_ui_state)
        self.use_connected_input_checkbox.toggled.connect(self.update_ui_state)
        
        # Populate with existing config
        has_arg = self.config.get("has_argument", False)
        use_connected = self.config.get("use_connected_input", False)
        
        self.has_argument_checkbox.setChecked(has_arg)
        self.use_connected_input_checkbox.setChecked(use_connected)
        self.argument_input.setText(str(self.config.get('argument_value', '')))
        
        self.update_ui_state()

    def update_ui_state(self):
        """Updates the visibility and enabled state of the input fields."""
        has_arg = self.has_argument_checkbox.isChecked()
        use_connected = self.use_connected_input_checkbox.isChecked()

        self.use_connected_input_checkbox.setVisible(has_arg)
        self.argument_input.setVisible(has_arg)

        # The static value input is only enabled if we have an argument AND
        # we are NOT using the value from a connection.
        self.argument_input.setEnabled(has_arg and not use_connected)

    def get_config(self):
        """Returns the updated configuration dictionary."""
        self.config['has_argument'] = self.has_argument_checkbox.isChecked()
        
        if self.config['has_argument']:
            self.config['use_connected_input'] = self.use_connected_input_checkbox.isChecked()
            if not self.config['use_connected_input']:
                self.config['argument_value'] = self.argument_input.text()
            else:
                # Clean up static value if not used
                self.config.pop('argument_value', None)
        else:
            # Clean up all argument keys if no argument is used
            self.config.pop('use_connected_input', None)
            self.config.pop('argument_value', None)
            
        return self.config
