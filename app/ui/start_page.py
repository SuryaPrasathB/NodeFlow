"""
Start Page Widget for the OPC-UA Client Application.

This module provides the StartPage, a welcome screen that allows users to
quickly create a new project, open an existing one, or select from a list
of recently opened projects.
"""
import os
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                             QListWidget, QListWidgetItem, QSizePolicy)
from PyQt6.QtCore import pyqtSignal, Qt, QSize
from PyQt6.QtGui import QFont, QIcon
from app.utils.paths import resource_path

class ActionCard(QPushButton):
    """
    A custom clickable card widget with an icon and text.

    This widget is styled to look like a modern UI card and is used on the
    start page for actions like "New Project" and "Open Project".
    """
    def __init__(self, text, icon_path, parent=None):
        """
        Initializes the ActionCard.

        Args:
            text (str): The text to display on the card.
            icon_path (str): The path to the icon to display on the card.
            parent (QWidget, optional): The parent widget. Defaults to None.
        """
        super().__init__(parent)
        self.setMinimumSize(150, 80)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        self.icon_label = QLabel()
        self.icon_label.setPixmap(QIcon(icon_path).pixmap(QSize(24, 24)))

        self.text_label = QLabel(text)

        layout.addWidget(self.icon_label)
        layout.addWidget(self.text_label)

        self.setStyleSheet("""
            QPushButton {
                border: 1px solid #444;
                background-color: #3c3f41;
                border-radius: 6px;
                text-align: left;
                padding: 10px;
            }
            QPushButton:hover {
                background-color: #4a4e52;
            }
            QLabel {
                background-color: transparent;
                border: none;
                font-size: 11pt;
            }
        """)

class StartPage(QWidget):
    """
    The initial welcome screen widget for the application.

    This page provides the main entry points for the user: creating a new
    project, opening an existing project, and accessing a list of recent
    projects. It emits signals to notify the main window of the user's choice.

    Attributes:
        new_project_requested (pyqtSignal): Emitted when the "New Project"
                                            card is clicked.
        open_project_requested (pyqtSignal): Emitted when the "Open Project"
                                             card is clicked.
        open_recent_project_requested (pyqtSignal): Emitted when a recent project
                                                    is selected. Passes the
                                                    project file path (str).
    """
    new_project_requested = pyqtSignal()
    open_project_requested = pyqtSignal()
    open_recent_project_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        """
        Initializes the StartPage.

        Args:
            parent (QWidget, optional): The parent widget. Defaults to None.
        """
        super().__init__(parent)

        outer_layout = QHBoxLayout(self)
        outer_layout.addStretch()

        container = QWidget()
        container.setMaximumWidth(700)
        main_layout = QVBoxLayout(container)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        main_layout.setSpacing(25)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # --- Title ---
        title_font = QFont()
        title_font.setPointSize(18)
        title_label = QLabel("OPC-UA Dashboard Client")
        title_label.setFont(title_font)

        # --- Action Cards ---
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(15)

        new_project_card = ActionCard("New Project", resource_path("app/resources/icons/new_file.png"))
        new_project_card.clicked.connect(self.new_project_requested)

        open_project_card = ActionCard("Open Project", resource_path("app/resources/icons/open_folder.png"))
        open_project_card.clicked.connect(self.open_project_requested)

        actions_layout.addWidget(new_project_card)
        actions_layout.addWidget(open_project_card)
        actions_layout.addStretch()

        # --- Recent Projects ---
        recent_layout = QVBoxLayout()
        recent_layout.setSpacing(10)
        recent_label = QLabel("Recent projects")
        recent_label.setStyleSheet("font-size: 12pt; font-weight: bold; margin-bottom: 5px;")

        self.recent_projects_list = QListWidget()
        self.recent_projects_list.itemDoubleClicked.connect(self.on_recent_item_clicked)
        self.recent_projects_list.setStyleSheet("""
            QListWidget {
                border: none;
                background-color: transparent;
            }
            QListWidget::item {
                padding: 4px;
                border-radius: 4px;
            }
            QListWidget::item:hover {
                background-color: #3c3f41;
            }
        """)

        recent_layout.addWidget(recent_label)
        recent_layout.addWidget(self.recent_projects_list)

        # --- Assemble Layout ---
        main_layout.addWidget(title_label)
        main_layout.addSpacing(15)
        main_layout.addLayout(actions_layout)
        main_layout.addSpacing(20)
        main_layout.addLayout(recent_layout)

        outer_layout.addWidget(container)
        outer_layout.addStretch()

    def populate_recent_projects(self, project_paths):
        """
        Clears and fills the recent projects list.

        Each project path is used to create a custom styled list item showing
        the project's name. If the list of paths is empty, it displays a
        "No recent projects" message.

        Args:
            project_paths (list[str]): A list of full paths to recent projects.
        """
        self.recent_projects_list.clear()
        if not project_paths:
            item = QListWidgetItem("No recent projects")
            item.setForeground(Qt.GlobalColor.gray)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            self.recent_projects_list.addItem(item)
            return

        for path in project_paths:
            if os.path.exists(path):
                file_name = os.path.basename(path)
                dir_name = os.path.dirname(path)

                item_widget = QWidget()
                item_layout = QVBoxLayout(item_widget)
                item_layout.setContentsMargins(5, 5, 5, 5)
                item_layout.setSpacing(0)

                name_label = QLabel(file_name)
                name_label.setStyleSheet("font-size: 11pt; min-height: 24px;")

                path_label = QLabel(dir_name)
                path_label.setStyleSheet("font-size: 9pt; color: #888;")

                item_layout.addWidget(name_label)
                #item_layout.addWidget(path_label)

                list_item = QListWidgetItem(self.recent_projects_list)
                list_item.setSizeHint(item_widget.sizeHint())
                list_item.setData(Qt.ItemDataRole.UserRole, path)

                self.recent_projects_list.addItem(list_item)
                self.recent_projects_list.setItemWidget(list_item, item_widget)

    def on_recent_item_clicked(self, item):
        """
        Handles the selection of a recent project from the list.

        Emits the `open_recent_project_requested` signal with the full path
        of the clicked project.

        Args:
            item (QListWidgetItem): The list widget item that was double-clicked.
        """
        full_path = item.data(Qt.ItemDataRole.UserRole)
        if full_path:
            self.open_recent_project_requested.emit(full_path)
