"""
Provides standardized dialog boxes for displaying errors and information.

This module contains utility functions that wrap QMessageBox to ensure a
consistent look and feel for feedback provided to the user throughout the
application.
"""
from PyQt6.QtWidgets import QMessageBox

def show_error_message(title, message, detailed_text=""):
    """
    Displays a standardized critical error message box.

    This function creates and shows a modal QMessageBox with a critical icon,
    a main title, an informative message, and optional detailed text.

    Args:
        title (str): The main title of the message box (will be bolded).
        message (str): The primary message to be displayed to the user.
        detailed_text (str, optional): Additional text that will be shown in a
                                       collapsible "Show Details" section.
                                       Defaults to "".
    """
    msg_box = QMessageBox()
    msg_box.setIcon(QMessageBox.Icon.Critical)
    msg_box.setText(f"<b>{title}</b>")
    msg_box.setInformativeText(message)
    if detailed_text:
        msg_box.setDetailedText(str(detailed_text))
    msg_box.setWindowTitle("Error")
    msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
    msg_box.exec()

def show_info_message(title, message):
    """
    Displays a standardized informational message box.

    This function creates and shows a modal QMessageBox with an information icon,
    a main title, and an informative message.

    Args:
        title (str): The main title of the message box (will be bolded).
        message (str): The primary message to be displayed to the user.
    """
    msg_box = QMessageBox()
    msg_box.setIcon(QMessageBox.Icon.Information)
    msg_box.setText(f"<b>{title}</b>")
    msg_box.setInformativeText(message)
    msg_box.setWindowTitle("Information")
    msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
    msg_box.exec()
