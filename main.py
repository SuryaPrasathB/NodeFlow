"""
Main Entry Point for the OPC-UA Client Application.

This script initializes the PyQt application, sets up the asyncio event loop using
qasync, loads user settings (like the theme), and launches the main window.
It also handles the graceful shutdown of the application.
"""
import sys
import asyncio
import logging
import os
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import QSettings
from qasync import QEventLoop

from app.utils.paths import resource_path
from app.ui.main_window import MainWindow

def main():
    """
    Initializes and runs the PyQt6 OPC-UA Client application.
    """
    # --- 1. Configure Logging ---
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    # --- 2. Initialize the Application ---
    app = QApplication(sys.argv)
    app.setOrganizationName("LSControlSystems")
    app.setApplicationName("OPCUA-Client")

    # Set the application icon
    app.setWindowIcon(QIcon(resource_path("app/resources/icons/app_icon.ico")))

    # --- 3. Load and Apply Theme ---
    settings = QSettings()
    theme_name = settings.value("theme", "Dark")
    style_sheet = ""
    try:
        filename = resource_path(f"app/resources/styles/{theme_name.lower()}_theme.qss")
        with open(filename, "r") as f:
            style_sheet = f.read()
        app.setStyleSheet(style_sheet)
        # Remove dotted focus rectangle from all buttons
        app.setStyleSheet(app.styleSheet() + "QPushButton { outline: none; }")
    except FileNotFoundError:
        logging.error(f"Could not load startup theme '{theme_name}'. File not found at '{filename}'.")

    # --- 4. Set up the Asyncio Event Loop ---
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    main_window = MainWindow()
    main_window.show()

    # --- 6. Run the Application ---
    with loop:
        try:
            loop.run_forever()
        except asyncio.CancelledError:
            pass
        except RuntimeError as e:
            if "Event loop is closed" in str(e):
                logging.warning("Ignoring expected 'Event loop is closed' error during shutdown.")
            else:
                raise

if __name__ == "__main__":
    main()
