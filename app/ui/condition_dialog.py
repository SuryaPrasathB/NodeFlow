"""
Provides a dialog for setting conditions on sequencer connections.

This module contains the ConditionDialog class, which allows users to define
the logic that governs whether a connection between two sequence nodes is
traversed. It supports both simple comparisons and complex Python expressions.
"""
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QComboBox,
                             QLineEdit, QDialogButtonBox, QWidget, QLabel)

class ConditionDialog(QDialog):
    """
    A dialog to set the condition for a sequence connection.

    This dialog allows for two modes of condition setting:
    1.  **Simple Comparison**: A straightforward comparison using common operators
        (e.g., ==, >, is True).
    2.  **Custom Expression**: A flexible Python expression that evaluates to
        True or False, using the keyword 'INPUT' to reference the output of
        the preceding node.

    The UI dynamically adjusts based on the selected mode.
    """
    def __init__(self, parent=None, current_condition=None):
        """
        Initializes the ConditionDialog.

        Args:
            parent (QWidget, optional): The parent widget. Defaults to None.
            current_condition (dict, optional): A dictionary representing the
                condition to be edited. If provided, the dialog will be
                pre-filled with this data. Defaults to None.
        """
        super().__init__(parent)
        self.setWindowTitle("Set Connection Condition")
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)

        # --- Mode Selection ---
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Simple Comparison", "Custom Expression"])
        layout.addWidget(self.mode_combo)

        # --- Widgets for each mode ---
        self.simple_widget = QWidget()
        self.expression_widget = QWidget()

        self._setup_simple_ui()
        self._setup_expression_ui()

        layout.addWidget(self.simple_widget)
        layout.addWidget(self.expression_widget)

        # --- Buttons ---
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self.mode_combo.currentTextChanged.connect(self.update_ui)

        # --- Load existing state ---
        if current_condition and current_condition.get('type') == 'expression':
            self.mode_combo.setCurrentText("Custom Expression")
            self.expression_input.setText(current_condition.get('expression', ''))
        else:
            self.mode_combo.setCurrentText("Simple Comparison")
            if current_condition:
                self.operator_combo.setCurrentText(current_condition.get('operator', 'is True'))
                self.value_input.setText(str(current_condition.get('value', '')))

        self.update_ui()

    def _setup_simple_ui(self):
        """Creates and configures the UI for the 'Simple Comparison' mode."""
        form_layout = QFormLayout(self.simple_widget)
        self.operator_combo = QComboBox()
        self.operator_combo.addItems(["No Condition", "==", "!=", ">", "<", ">=", "<=", "is True", "is False"])
        form_layout.addRow("Condition:", self.operator_combo)
        self.value_input = QLineEdit()
        self.value_input.setPlaceholderText("e.g., 100 or 'Success'")
        form_layout.addRow("Value:", self.value_input)
        self.operator_combo.currentTextChanged.connect(self._update_simple_ui)

    def _setup_expression_ui(self):
        """Creates and configures the UI for the 'Custom Expression' mode."""
        expr_layout = QVBoxLayout(self.expression_widget)
        info_label = QLabel("Use '<b>INPUT</b>' as the variable for the previous node's output.<br>"
                            "The expression must evaluate to True or False.")
        info_label.setWordWrap(True)
        self.expression_input = QLineEdit()
        self.expression_input.setPlaceholderText("e.g., INPUT > 10 and INPUT < 20")
        self.expression_input.setStyleSheet("font-family: Consolas, Courier New, monospace;")
        expr_layout.addWidget(info_label)
        expr_layout.addWidget(self.expression_input)

    def update_ui(self):
        """
        Updates the visibility of the UI sections based on the selected mode.
        """
        mode = self.mode_combo.currentText()
        is_simple = (mode == "Simple Comparison")
        self.simple_widget.setVisible(is_simple)
        self.expression_widget.setVisible(not is_simple)
        if is_simple:
            self._update_simple_ui()

    def _update_simple_ui(self):
        """
        Hides or shows the 'Value' input field based on the selected operator.

        For unary operators like "is True" or "is False", the value input is hidden.
        """
        op = self.operator_combo.currentText()
        is_unary = op in ["is True", "is False", "No Condition"]
        self.value_input.setVisible(not is_unary)

    def get_condition(self):
        """
        Retrieves the configured condition from the dialog's fields.

        Returns:
            dict: A dictionary representing the configured condition. The
                  structure of the dictionary depends on the selected mode.
                  For 'simple': {'type': 'simple', 'operator': str, 'value': str}
                  For 'expression': {'type': 'expression', 'expression': str}
        """
        mode = self.mode_combo.currentText()
        if mode == "Simple Comparison":
            op = self.operator_combo.currentText()
            is_unary = op in ["is True", "is False", "No Condition"]
            return {
                "type": "simple",
                "operator": op,
                "value": None if is_unary else self.value_input.text()
            }
        else: # Custom Expression
            return {
                "type": "expression",
                "expression": self.expression_input.text()
            }
