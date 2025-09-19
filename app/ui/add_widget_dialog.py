"""
Provides a dialog for adding and configuring new UI widgets.

This module contains the AddWidgetDialog class, which allows users to define
the properties of a new widget, such as its type, label, and associated
OPC-UA node. The dialog can be used to create new widgets or edit existing ones.
"""
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QComboBox,
                             QLineEdit, QDialogButtonBox, QLabel, QCheckBox)
from PyQt6.QtCore import pyqtSignal
from .error_dialog import show_error_message

class AddWidgetDialog(QDialog):
    """
    A dialog for users to add a new widget or edit an existing one.

    This dialog provides a form to configure a widget's properties. It operates
    non-modally and emits a signal with the configuration data upon successful
    validation. The form fields dynamically adjust based on the selected widget type.

    Attributes:
        config_accepted (pyqtSignal): A signal that emits the widget
                                      configuration (dict) when the user clicks 'OK'.
    """
    config_accepted = pyqtSignal(dict)

    def __init__(self, parent=None, config_to_edit=None, is_from_tree=False):
        """
        Initializes the AddWidgetDialog.

        Args:
            parent (QWidget, optional): The parent widget. Defaults to None.
            config_to_edit (dict, optional): A dictionary containing the
                configuration of an existing widget to be edited. If None, the
                dialog will be in "add new" mode. Defaults to None.
            is_from_tree (bool, optional): Flag indicating if the widget is being
                configured from the OPC-UA server tree. This may make some
                fields read-only. Defaults to False.
        """
        super().__init__(parent)
        self.config_to_edit = config_to_edit
        self.is_from_tree = is_from_tree

        self.is_edit_mode = self.config_to_edit is not None
        title = "Configure New Widget" if self.is_from_tree else ("Edit Widget" if self.is_edit_mode else "Add New Widget Manually")
        self.setWindowTitle(title)
        self.setMinimumWidth(450)

        layout = QVBoxLayout(self)
        self.form_layout = QFormLayout()

        # --- Form Widgets ---
        self.widget_type_combo = QComboBox()
        self.widget_type_combo.addItems([
            "Numerical Display", "Text Display", "Switch",
            "String Input", "Numerical Input", "Button",
            "Sequence Button", "Plotter"
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

        self.buffer_size_label = QLabel("Buffer Size:")
        self.buffer_size_input = QLineEdit()
        self.buffer_size_input.setPlaceholderText("e.g., 100")
        self.form_layout.addRow(self.buffer_size_label, self.buffer_size_input)

        layout.addLayout(self.form_layout)

        # --- Dialog Buttons ---
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.validate_and_accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self.widget_type_combo.currentTextChanged.connect(self.update_form)

        if self.is_edit_mode:
            self.populate_form(self.config_to_edit)

        self.update_form()

    def validate_and_accept(self):
        """
        Validates the form input and, if successful, emits the configuration and closes.

        Checks for required fields based on the selected widget type. If validation
        fails, an error message is shown. If it succeeds, the `config_accepted`
        signal is emitted and the dialog is accepted.
        """
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

        self.config_accepted.emit(config)
        self.accept()

    def update_form(self, text=None):
        """
        Updates the visibility of form fields based on the selected widget type.

        This method is connected to the `currentTextChanged` signal of the
        widget type combo box. It ensures that only relevant options are
        displayed for the chosen widget.

        Args:
            text (str, optional): The current text of the combo box. Not used.
                                  Defaults to None.
        """
        widget_type = self.widget_type_combo.currentText()
        is_button = (widget_type == "Button")
        is_sequence = (widget_type == "Sequence Button")
        is_plotter = (widget_type == "Plotter")
        is_standard_node = not is_button and not is_sequence and not is_plotter

        # Toggle visibility based on widget type
        self.buffer_size_label.setVisible(is_plotter)
        self.buffer_size_input.setVisible(is_plotter)

        self.method_bname_label.setVisible(is_button)
        self.method_bname_input.setVisible(is_button)
        self.has_argument_label.setVisible(is_button)
        self.has_argument_checkbox.setVisible(is_button)

        self.identifier_label.setVisible(is_standard_node or is_button)
        self.identifier_input.setVisible(is_standard_node or is_button)

        self.sequence_name_label.setVisible(is_sequence)
        self.sequence_name_input.setVisible(is_sequence)

        # Update label text for clarity
        if is_button:
            self.identifier_label.setText("Parent Node ID:")
        else:
            self.identifier_label.setText("Node ID:")

    def populate_form(self, config):
        """
        Fills the form with data from an existing widget's configuration.

        This is used when the dialog is opened in "edit" mode.

        Args:
            config (dict): The configuration dictionary of the widget to edit.
        """
        self.widget_type_combo.setCurrentText(config.get("widget_type", ""))
        self.label_input.setText(config.get("label", ""))
        self.identifier_input.setText(config.get("identifier", ""))
        self.sequence_name_input.setText(config.get("sequence_name", ""))
        self.buffer_size_input.setText(str(config.get("buffer_size", 100)))

        if self.is_from_tree:
            self.identifier_input.setReadOnly(True)

        if config.get("widget_type") == "Button":
            self.method_bname_input.setText(config.get("method_bname", ""))
            self.has_argument_checkbox.setChecked(config.get("has_argument", False))
            if self.is_from_tree:
                self.method_bname_input.setReadOnly(True)

        self.update_form()

    def get_config(self):
        """
        Retrieves the current configuration from the form fields.

        Returns:
            dict: A dictionary containing the widget configuration.
        """
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
        elif widget_type == "Plotter":
            config["buffer_size"] = int(self.buffer_size_input.text()) if self.buffer_size_input.text().isdigit() else 100

        return config
