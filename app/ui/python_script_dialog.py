"""
Provides a dialog for editing Python code with syntax highlighting.

This module contains the PythonScriptDialog, which embeds a QPlainTextEdit
with a custom QSyntaxHighlighter for editing Python scripts within the application.
"""
import sys
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QPlainTextEdit, QDialogButtonBox, QPushButton)
from PyQt6.QtCore import QRegularExpression
from PyQt6.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor, QFont
from .error_dialog import show_error_message, show_info_message

from pygments import highlight
from pygments.lexers.python import PythonLexer
from pygments.formatters.html import HtmlFormatter

class PythonSyntaxHighlighter(QSyntaxHighlighter):
    """
    A syntax highlighter for Python code.

    This class implements basic syntax highlighting for common Python keywords,
    strings (single and double quoted), and comments. It applies different
    character formats to these elements within a QPlainTextEdit document.
    """
    def __init__(self, parent):
        """
        Initializes the PythonSyntaxHighlighter.

        Args:
            parent (QTextDocument): The document to which the highlighter is applied.
        """
        super().__init__(parent)
        self.formatter = HtmlFormatter(style='monokai')
        self.lexer = PythonLexer()

    def highlightBlock(self, text):
        """
        Applies syntax highlighting to a block of text.

        This method is called by Qt whenever a block of text needs to be
        redrawn. It uses regular expressions to find keywords, strings, and
        comments and applies the corresponding formats.

        Args:
            text (str): The block of text to highlight.
        """
        # A simple keyword highlighter
        keyword_format = QTextCharFormat()
        keyword_format.setForeground(QColor("#fc5e03"))
        keyword_format.setFontWeight(QFont.Weight.Bold)

        keywords = [
            "\\bdef\\b", "\\bclass\\b", "\\bimport\\b", "\\bfrom\\b",
            "\\breturn\\b", "\\bif\\b", "\\belif\\b", "\\belse\\b",
            "\\bfor\\b", "\\bin\\b", "\\bwhile\\b", "\\bbreak\\b",
            "\\bcontinue\\b", "\\bpass\\b", "\\btry\\b", "\\bexcept\\b",
            "\\bfinally\\b", "\\braise\\b", "\\bwith\\b", "\\bas\\b",
            "\\bassert\\b", "\\bdel\\b", "\\bglobal\\b", "\\bnonlocal\\b",
            "\\blambda\\b", "\\byield\\b", "\\bTrue\\b", "\\bFalse\\b",
            "\\bNone\\b"
        ]

        for pattern in keywords:
            expression = QRegularExpression(pattern)
            it = expression.globalMatch(text)
            while it.hasNext():
                match = it.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), keyword_format)

        # String highlighter
        string_format = QTextCharFormat()
        string_format.setForeground(QColor("#e6db74"))

        # Single-quoted strings
        expression = QRegularExpression("'[^']*'")
        it = expression.globalMatch(text)
        while it.hasNext():
            match = it.next()
            self.setFormat(match.capturedStart(), match.capturedLength(), string_format)

        # Double-quoted strings
        expression = QRegularExpression("\"[^\"]*\"")
        it = expression.globalMatch(text)
        while it.hasNext():
            match = it.next()
            self.setFormat(match.capturedStart(), match.capturedLength(), string_format)

        # Comment highlighter
        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor("#75715e"))
        comment_format.setFontItalic(True)

        expression = QRegularExpression("#[^\n]*")
        it = expression.globalMatch(text)
        while it.hasNext():
            match = it.next()
            self.setFormat(match.capturedStart(), match.capturedLength(), comment_format)


class PythonScriptDialog(QDialog):
    """
    A dialog for editing a Python script.

    This dialog provides a text editor with syntax highlighting for writing
    and modifying Python scripts associated with a Python Script Node in the
    sequencer.
    """
    def __init__(self, parent=None, script=""):
        """
        Initializes the PythonScriptDialog.

        Args:
            parent (QWidget, optional): The parent widget. Defaults to None.
            script (str, optional): The initial script text to load into the
                                    editor. Defaults to "".
        """
        super().__init__(parent)
        self.setWindowTitle("Python Script Node")
        self.resize(700, 500)

        layout = QVBoxLayout(self)

        self.editor = QPlainTextEdit()
        self.editor.setPlainText(script)
        font = QFont()
        font.setFamily("Courier New")
        font.setPointSize(12)
        self.editor.setFont(font)

        self.highlighter = PythonSyntaxHighlighter(self.editor.document())

        layout.addWidget(self.editor)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        
        # --- FEATURE: VERIFY SCRIPT ---
        self.verify_button = QPushButton("Verify")
        self.verify_button.clicked.connect(self.verify_script)
        button_box.addButton(self.verify_button, QDialogButtonBox.ButtonRole.ActionRole)

        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def verify_script(self):
        """
        Verifies the syntax of the Python script in the editor.
        """
        script = self.get_script()
        try:
            compile(script, '<string>', 'exec')
            show_info_message("Syntax OK", "The script syntax is valid.")
        except SyntaxError as e:
            show_error_message("Syntax Error", f"The script has a syntax error:\n\n{e}")

    def get_script(self):
        """
        Retrieves the script text from the editor.

        Returns:
            str: The Python script as a string.
        """
        return self.editor.toPlainText()
