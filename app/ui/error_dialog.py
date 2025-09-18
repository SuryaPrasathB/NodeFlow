from PyQt6.QtWidgets import QMessageBox

def show_error_message(title, message, detailed_text=""):
    """
    Displays a standardized error message box.
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
    Displays a standardized info message box.
    """
    msg_box = QMessageBox()
    msg_box.setIcon(QMessageBox.Icon.Information)
    msg_box.setText(f"<b>{title}</b>")
    msg_box.setInformativeText(message)
    msg_box.setWindowTitle("Information")
    msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
    msg_box.exec()
