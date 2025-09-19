"""
Provides configuration dialogs for various sequencer nodes.

This module contains dialog windows used to configure the properties of
different nodes in the sequencer, such as setting method arguments or
defining expressions.
"""
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QLineEdit,
                             QDialogButtonBox, QCheckBox, QLabel)

class NodeConfigDialog(QDialog):
    """
    A dialog to configure a Method Call node in the sequencer.

    This dialog allows the user to specify whether a method call should include
    an argument. If an argument is included, the user can choose to provide a
    static value or to use the value from an incoming data connection.
    """
    def __init__(self, parent=None, current_config=None):
        """
        Initializes the NodeConfigDialog.

        Args:
            parent (QWidget, optional): The parent widget. Defaults to None.
            current_config (dict, optional): A dictionary containing the
                current configuration of the node. If provided, the dialog
                will be pre-filled with this data. Defaults to None.
        """
        super().__init__(parent)
        self.setWindowTitle("Configure Method Node")
        self.config = current_config or {}

        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        self.method_label = QLabel(f"<b>{self.config.get('label', 'N/A')}</b>")
        form_layout.addRow("Method:", self.method_label)

        self.has_argument_checkbox = QCheckBox("Pass Input Argument")
        form_layout.addRow(self.has_argument_checkbox)

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
        """
        Updates the visibility and enabled state of the input fields.

        This method dynamically shows or hides the argument-related options
        based on the state of the checkboxes, ensuring a clean user experience.
        """
        has_arg = self.has_argument_checkbox.isChecked()
        use_connected = self.use_connected_input_checkbox.isChecked()

        self.use_connected_input_checkbox.setVisible(has_arg)
        self.argument_input.setVisible(has_arg)

        # The static value input is only enabled if we have an argument AND
        # we are NOT using the value from a connection.
        self.argument_input.setEnabled(has_arg and not use_connected)

    def get_config(self):
        """
        Retrieves the updated configuration from the dialog's fields.

        This method compiles the user's choices into a dictionary. It also
        cleans up unnecessary keys from the configuration to keep it tidy.

        Returns:
            dict: The updated configuration dictionary for the node.
        """
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
