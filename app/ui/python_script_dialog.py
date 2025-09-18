import sys
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QPlainTextEdit, QDialogButtonBox)
from PyQt6.QtCore import QRegularExpression
from PyQt6.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor, QFont

from pygments import highlight
from pygments.lexers.python import PythonLexer
from pygments.formatters.html import HtmlFormatter

class PythonSyntaxHighlighter(QSyntaxHighlighter):
    def __init__(self, parent):
        super().__init__(parent)
        self.formatter = HtmlFormatter(style='monokai')
        self.lexer = PythonLexer()

    def highlightBlock(self, text):
        # Use pygments to get HTML with inline styles
        html = highlight(text, self.lexer, self.formatter)

        # This is a simplified approach. A more robust implementation would
        # parse the HTML and apply formats. For now, we will just set a default
        # color for the whole block. A proper implementation would be more complex.

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
    def __init__(self, parent=None, script=""):
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
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def get_script(self):
        return self.editor.toPlainText()
