from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QComboBox, 
                             QLineEdit, QDialogButtonBox, QLabel, QCheckBox)
from PyQt6.QtCore import pyqtSignal
from .error_dialog import show_error_message

class AddWidgetDialog(QDialog):
    """
    A dialog for users to add a new widget or edit a pre-filled one.
    This dialog is non-modal and emits a signal with the config on success.
    """
    # FIX: Re-added the signal required for non-modal operation.
    config_accepted = pyqtSignal(dict)

    def __init__(self, parent=None, config_to_edit=None, is_from_tree=False):
        super().__init__(parent)
        self.config_to_edit = config_to_edit
        self.is_from_tree = is_from_tree
        
        self.is_edit_mode = self.config_to_edit is not None
        title = "Configure New Widget" if self.is_from_tree else ("Edit Widget" if self.is_edit_mode else "Add New Widget Manually")
        self.setWindowTitle(title)
        self.setMinimumWidth(450)

        layout = QVBoxLayout(self)
        self.form_layout = QFormLayout()

        self.widget_type_combo = QComboBox()
        self.widget_type_combo.addItems([
            "Numerical Display", "Text Display", "Switch", 
            "String Input", "Numerical Input", "Button",
            "Sequence Button"
        ])
        self.form_layout.addRow("Widget Type:", self.widget_type_combo)

        self.label_input = QLineEdit()
        self.label_input.setPlaceholderText("e.g., Pump Speed or Start Motor")
        self.form_layout.addRow("Widget Label:", self.label_input)

        self.identifier_label = QLabel("Node ID:")
        self.identifier_input = QLineEdit()
        self.identifier_input.setPlaceholderText("e.g., ns=2;i=1234")
        self.form_layout.addRow(self.identifier_label, self.identifier_input)

        self.method_bname_label = QLabel("Method BrowseName:")
        self.method_bname_input = QLineEdit()
        self.method_bname_input.setPlaceholderText("e.g., StartMotor or SetValue")
        self.has_argument_label = QLabel("Method Argument:")
        self.has_argument_checkbox = QCheckBox("Has Input Argument?")
        self.form_layout.addRow(self.method_bname_label, self.method_bname_input)
        self.form_layout.addRow(self.has_argument_label, self.has_argument_checkbox)

        self.sequence_name_label = QLabel("Sequence Name:")
        self.sequence_name_input = QLineEdit()
        self.sequence_name_input.setPlaceholderText("Enter the name of the sequence to run")
        self.form_layout.addRow(self.sequence_name_label, self.sequence_name_input)
        
        layout.addLayout(self.form_layout)
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.validate_and_accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self.widget_type_combo.currentTextChanged.connect(self.update_form)
        
        if self.is_edit_mode:
            self.populate_form(self.config_to_edit)
        
        self.update_form()

    def validate_and_accept(self):
        config = self.get_config()
        if not config.get("label"):
            show_error_message("Validation Failed", "The 'Widget Label' field cannot be empty.")
            return

        if config["widget_type"] == "Sequence Button" and not config.get("sequence_name"):
            show_error_message("Validation Failed", "The 'Sequence Name' is required for a Sequence Button.")
            return

        if config["widget_type"] not in ["Sequence Button"] and not config.get("identifier"):
            show_error_message("Validation Failed", "The 'Node ID' field cannot be empty.")
            return

        if config.get("widget_type") == "Button" and not config.get("method_bname"):
            show_error_message("Validation Failed", "The 'Method BrowseName' is required for a Button widget.")
            return
            
        # FIX: Emit the signal with the config data and then close the dialog.
        self.config_accepted.emit(config)
        self.accept()

    def update_form(self, text=None):
        widget_type = self.widget_type_combo.currentText()
        is_button = (widget_type == "Button")
        is_sequence = (widget_type == "Sequence Button")
        is_standard_node = not is_button and not is_sequence

        self.method_bname_label.setVisible(is_button)
        self.method_bname_input.setVisible(is_button)
        self.has_argument_label.setVisible(is_button)
        self.has_argument_checkbox.setVisible(is_button)
        
        self.identifier_label.setVisible(is_standard_node or is_button)
        self.identifier_input.setVisible(is_standard_node or is_button)

        self.sequence_name_label.setVisible(is_sequence)
        self.sequence_name_input.setVisible(is_sequence)
        
        if is_button:
            self.identifier_label.setText("Parent Node ID:")
        else:
            self.identifier_label.setText("Node ID:")

    def populate_form(self, config):
        self.widget_type_combo.setCurrentText(config.get("widget_type", ""))
        self.label_input.setText(config.get("label", ""))
        self.identifier_input.setText(config.get("identifier", ""))
        self.sequence_name_input.setText(config.get("sequence_name", ""))
        
        if self.is_from_tree:
            self.identifier_input.setReadOnly(True)
        
        if config.get("widget_type") == "Button":
            self.method_bname_input.setText(config.get("method_bname", ""))
            self.has_argument_checkbox.setChecked(config.get("has_argument", False))
            if self.is_from_tree:
                self.method_bname_input.setReadOnly(True)
        
        self.update_form()

    def get_config(self):
        config = {
            "widget_type": self.widget_type_combo.currentText(),
            "label": self.label_input.text(),
        }
        widget_type = config["widget_type"]
        
        if widget_type == "Sequence Button":
            config["sequence_name"] = self.sequence_name_input.text()
        else:
            config["search_type"] = "By Node ID"
            config["identifier"] = self.identifier_input.text()

        if widget_type == "Button":
            config["method_bname"] = self.method_bname_input.text()
            config["has_argument"] = self.has_argument_checkbox.isChecked()
            
        return config
