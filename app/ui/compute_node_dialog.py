"""
Provides a configuration dialog for the Compute Node in the sequencer.

This module contains the ComputeNodeDialog class, which allows users to
input a Python expression to be evaluated by a ComputeNode.
"""
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QLineEdit,
                             QDialogButtonBox, QLabel)

class ComputeNodeDialog(QDialog):
    """
    A dialog for configuring the Python expression of a ComputeNode.

    This dialog presents an input field for the user to define a mathematical
    or logical expression. It also provides instructions on how to reference
    the node's inputs ('A', 'B', 'C') within the expression.
    """
    def __init__(self, parent=None, current_config=None):
        """
        Initializes the ComputeNodeDialog.

        Args:
            parent (QWidget, optional): The parent widget. Defaults to None.
            current_config (dict, optional): A dictionary containing the
                current configuration of the node. If provided, the dialog
                will be pre-filled with this data. Defaults to None.
        """
        super().__init__(parent)
        self.setWindowTitle("Configure Compute Node")
        self.config = current_config or {}

        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        # Add a label explaining how to use the inputs
        info_label = QLabel("Use 'A', 'B', and 'C' as variables from the data inputs.\n"
                            "The expression should evaluate to a single value.\n"
                            "Example: (A * 2) + B > C")
        info_label.setWordWrap(True)

        self.expression_input = QLineEdit()
        self.expression_input.setPlaceholderText("e.g., A - B == 5")
        self.expression_input.setStyleSheet("font-family: Consolas, Courier New, monospace;")

        form_layout.addRow(info_label)
        form_layout.addRow("Expression:", self.expression_input)

        layout.addLayout(form_layout)
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        # Load existing settings
        self.expression_input.setText(self.config.get('expression', ''))

    def get_config(self):
        """
        Retrieves the updated configuration from the dialog.

        This method reads the text from the expression input field, updates
        the configuration dictionary, and also generates a descriptive label
        for the node based on a snippet of the expression.

        Returns:
            dict: The updated configuration dictionary for the ComputeNode.
        """
        self.config['expression'] = self.expression_input.text()
        # Update the node's label to show a snippet of the expression
        expr_snippet = self.config['expression']
        if len(expr_snippet) > 15:
            expr_snippet = expr_snippet[:12] + "..."
        self.config['label'] = f"Compute: {expr_snippet}"
        return self.config