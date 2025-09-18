"""
Main Window and UI Orchestrator for the OPC-UA Client.

This module contains the MainWindow class, which is the central hub of the
application. It constructs the UI, including the toolbar, docks, and tabbed
interface for the dashboard and sequencer. It also manages the application's
state, handles user actions, and orchestrates communication between the UI
components and the core OPC-UA logic.
"""
import asyncio
import json
import logging
import os
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
                             QPushButton, QLabel, QToolBar, QApplication, QFileDialog,
                             QDockWidget, QStackedWidget, QMessageBox, QTabWidget, QComboBox,
                             QInputDialog, QSizePolicy, QMenuBar, QDialog, QFormLayout, 
                             QDialogButtonBox, QCheckBox)
from PyQt6.QtGui import QAction, QIcon, QPainter, QPen, QColor, QKeySequence, QCursor, QPixmap
from PyQt6.QtCore import pyqtSignal, QObject, Qt, QSize, QTimer, QSettings, QPoint, QLine

# --- Local Imports ---
from app.utils.paths import resource_path
from app.core.opcua_logic import OpcuaClientLogic
from app.ui.add_widget_dialog import AddWidgetDialog
from app.utils.logger import LogWidget, QtLogHandler
from app.ui.error_dialog import show_error_message, show_info_message
from app.ui.server_tree import ServerTreeView
from app.ui.sequencer_editor import SequenceEditor, SequenceEngine
from app.ui.sequence_tree import SequenceTreeView
from app.ui.settings_dialog import SettingsDialog
from app.ui.widgets.sequence_widget import SequenceWidget
from app.ui.widgets.base_widget import BaseWidget
from app.ui.start_page import StartPage
from app.ui.global_find_dialog import GlobalFindDialog
from app.ui.widgets.display_widget import DisplayWidget
from app.ui.widgets.switch_widget import SwitchWidget
from app.ui.widgets.input_widget import InputWidget
from app.ui.widgets.button_widget import ButtonWidget

class ServerSettingsDialog(QDialog):
    """Dialog for configuring server connection settings."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Server Settings")
        self.resize(500, 200)

        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        self.url_input = QLineEdit()
        self.auth_checkbox = QCheckBox("Enable Authentication")
        self.user_input = QLineEdit()
        self.pass_input = QLineEdit()
        self.pass_input.setEchoMode(QLineEdit.EchoMode.Password)

        form_layout.addRow("Server URL:", self.url_input)
        form_layout.addRow(self.auth_checkbox)
        form_layout.addRow("Username:", self.user_input)
        form_layout.addRow("Password:", self.pass_input)
        
        layout.addLayout(form_layout)
        
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self.auth_checkbox.toggled.connect(self.toggle_auth_fields)
        self.load_settings()
        self.toggle_auth_fields(self.auth_checkbox.isChecked())

    def toggle_auth_fields(self, checked):
        self.user_input.setEnabled(checked)
        self.pass_input.setEnabled(checked)

    def load_settings(self):
        settings = QSettings("MyCompany", "OPCUA-Client")
        self.url_input.setText(settings.value("server_url", "opc.tcp://localhost:4840/freeopcua/server/"))
        self.auth_checkbox.setChecked(settings.value("auth_enabled", False, type=bool))
        self.user_input.setText(settings.value("username", ""))
        self.pass_input.setText(settings.value("password", ""))

    def save_settings(self):
        settings = QSettings("MyCompany", "OPCUA-Client")
        settings.setValue("server_url", self.url_input.text())
        settings.setValue("auth_enabled", self.auth_checkbox.isChecked())
        settings.setValue("username", self.user_input.text())
        settings.setValue("password", self.pass_input.text())

    def accept(self):
        self.save_settings()
        super().accept()

# A simple widget to draw a colored circle for status indication.
class StatusIndicator(QWidget):
    """A simple colored circle to indicate connection status."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(16, 16)
        self.label = QLabel(self)
        self.label.setFixedSize(16, 16)
        self.label.setScaledContents(True)
        self.red_pixmap = QPixmap(resource_path("app/resources/icons/red_circle.png"))
        self.green_pixmap = QPixmap(resource_path("app/resources/icons/green_circle.png"))
        self.label.setPixmap(self.red_pixmap)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.label)

    def set_state(self, is_connected):
        """Sets the image of the circle based on the connection state."""
        if is_connected:
            self.label.setPixmap(self.green_pixmap)
        else:
            self.label.setPixmap(self.red_pixmap)

class CustomTitleBar(QWidget):
    """A custom title bar widget with an integrated menu bar and window controls."""
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.setAutoFillBackground(True)
        self.setBackgroundRole(parent.backgroundRole())
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 0, 0, 0)
        layout.setSpacing(5)

        # --- Icon ---
        self.icon_label = QLabel()
        icon = QIcon(resource_path("app/resources/icons/app_icon.ico"))
        self.icon_label.setPixmap(icon.pixmap(QSize(22, 22)))
        layout.addWidget(self.icon_label)

        # --- Menu Bar ---
        self.menu_bar = QMenuBar()
        self.menu_bar.setStyleSheet("""
            QMenuBar { padding: 2px 5px; }
            QMenuBar::item { padding: 4px 8px; }
            QMenuBar::item:selected { background-color: #555; }
            QMenu::item:selected { background-color: #555; }
        """)
        layout.addWidget(self.menu_bar)

        # --- Title ---
        self.title_label = QLabel("NodeFlow")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setStyleSheet("font-size: 10pt;")
        layout.addWidget(self.title_label)

        layout.addStretch()

        # --- Connection Status Indicator ---
        self.status_label = QLabel("Server Disconnected")
        self.status_label.setStyleSheet("font-size: 9pt; color: #aaa; margin-right: 5px;")
        self.status_indicator = StatusIndicator(self)
        layout.addWidget(self.status_label)
        layout.addWidget(self.status_indicator)
        layout.addSpacing(10) # Add some space before window controls

        # --- Window Controls (Text) ---
        self.minimize_button    = QPushButton()
        self.minimize_button.setToolTip("Minimize")
        self.minimize_button.setIcon(QIcon(resource_path("app/resources/icons/minimize.png")))
        
        self.maximize_button    = QPushButton()
        self.maximize_button.setToolTip("Maximize")
        self.maximize_button.setIcon(QIcon(resource_path("app/resources/icons/maximize.png")))
        
        self.close_button       = QPushButton()
        self.close_button.setToolTip("Close")
        self.close_button.setIcon(QIcon(resource_path("app/resources/icons/close.png")))

        for btn in [self.minimize_button, self.maximize_button, self.close_button]:
            btn.setFixedSize(30, 30)
            btn.setStyleSheet("""
                QPushButton { border: none; background-color: transparent; font-size: 14pt; }
                QPushButton:hover { background-color: #555; }
            """)

        self.close_button.setStyleSheet("""
            QPushButton { border: none; background-color: transparent; font-size: 14pt; }
            QPushButton:hover { background-color: #e81123; }
        """)

        layout.addWidget(self.minimize_button)
        layout.addWidget(self.maximize_button)
        layout.addWidget(self.close_button)

        self.minimize_button.clicked.connect(parent.showMinimized)
        self.maximize_button.clicked.connect(self.toggle_maximize)
        self.close_button.clicked.connect(parent.close)

        self.start_pos = None
        self.is_dragging = False

    def mouseDoubleClickEvent(self, event):
        """Handles double-clicking on the title bar to maximize/restore the window."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.toggle_maximize()

    def set_connection_status(self, is_connected):
        """Updates the text and color of the status indicator."""
        if is_connected:
            self.status_label.setText("Server Connected")
            self.status_indicator.set_state(True)  # Green
        else:
            self.status_label.setText("Server Disconnected")
            self.status_indicator.set_state(False) # Red

    def toggle_maximize(self):
        if self.parent.isMaximized():
            self.parent.showNormal()
        else:
            self.parent.showMaximized()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # Prevent dragging if the click is on the menu bar
            if event.pos().x() > self.menu_bar.width():
                self.start_pos = event.globalPosition().toPoint()
                self.is_dragging = True

    def mouseMoveEvent(self, event):
        if self.is_dragging and self.start_pos:
            delta = event.globalPosition().toPoint() - self.start_pos
            self.parent.move(self.parent.pos() + delta)
            self.start_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        self.start_pos = None
        self.is_dragging = False

class AsyncRunner(QObject):
    run_task_signal = pyqtSignal(object)
    def __init__(self):
        super().__init__()
        self.run_task_signal.connect(self.run_task)
    def run_task(self, coro):
        loop = asyncio.get_event_loop()
        loop.create_task(coro)
    def submit(self, coro):
        self.run_task_signal.emit(coro)

class DashboardGrid(QWidget):
    """
    A widget that paints a background grid, handles clearing widget selections
    when the background is clicked, and shows visual alignment guides.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.grid_size = 20
        self.dragged_widget = None
        self.alignment_lines = []
        
    def mousePressEvent(self, event):
        child = self.childAt(event.pos())
        if child is None:
            for widget in self.findChildren(BaseWidget):
                widget.setSelected(False)
        
        super().mousePressEvent(event)

    def set_dragged_widget(self, widget):
        self.dragged_widget = widget
        self.update() 

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        
        pen = QPen(QColor(45, 50, 60), 1, Qt.PenStyle.SolidLine)
        painter.setPen(pen)
        for x in range(0, self.width(), self.grid_size):
            painter.drawLine(x, 0, x, self.height())
        for y in range(0, self.height(), self.grid_size):
            painter.drawLine(0, y, self.width(), y)

        if self.dragged_widget:
            self.calculate_alignment_lines()
            pen = QPen(QColor(255, 0, 0, 150), 1, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            for line in self.alignment_lines:
                painter.drawLine(line)

    def calculate_alignment_lines(self):
        self.alignment_lines = []
        if not self.dragged_widget:
            return

        dragged_rect = self.dragged_widget.geometry()
        snap_threshold = 5
        
        other_widgets = [w for w in self.parent().findChildren(QWidget) if isinstance(w, BaseWidget) and w is not self.dragged_widget]

        dragged_edges = {
            'left': dragged_rect.left(), 'right': dragged_rect.right(),
            'top': dragged_rect.top(), 'bottom': dragged_rect.bottom(),
            'h_center': dragged_rect.center().x(), 'v_center': dragged_rect.center().y()
        }

        for other in other_widgets:
            other_rect = other.geometry()
            other_edges = {
                'left': other_rect.left(), 'right': other_rect.right(),
                'top': other_rect.top(), 'bottom': other_rect.bottom(),
                'h_center': other_rect.center().x(), 'v_center': other_rect.center().y()
            }

            for d_edge_name, d_edge_pos in dragged_edges.items():
                if 'h_' in d_edge_name or d_edge_name in ['left', 'right']:
                    for o_edge_name, o_edge_pos in other_edges.items():
                        if 'h_' in o_edge_name or o_edge_name in ['left', 'right']:
                            if abs(d_edge_pos - o_edge_pos) < snap_threshold:
                                y1 = min(dragged_rect.top(), other_rect.top())
                                y2 = max(dragged_rect.bottom(), other_rect.bottom())
                                self.alignment_lines.append(QLine(o_edge_pos, y1, o_edge_pos, y2))

            for d_edge_name, d_edge_pos in dragged_edges.items():
                if 'v_' in d_edge_name or d_edge_name in ['top', 'bottom']:
                    for o_edge_name, o_edge_pos in other_edges.items():
                        if 'v_' in o_edge_name or o_edge_name in ['top', 'bottom']:
                            if abs(d_edge_pos - o_edge_pos) < snap_threshold:
                                x1 = min(dragged_rect.left(), other_rect.left())
                                x2 = max(dragged_rect.right(), other_rect.right())
                                self.alignment_lines.append(QLine(x1, o_edge_pos, x2, o_edge_pos))

class MainWindow(QMainWindow):
    connection_success = pyqtSignal()
    connection_failed = pyqtSignal(str, str)
    disconnection_finished = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setMouseTracking(True) # Required for hover-based resize cursors
        
        self.border_thickness = 8 # The thickness of the invisible resize border
        
        self.active_find_widget = None

        self.opcua_logic = OpcuaClientLogic()
        self.opcua_logic.connection_lost_callback = self.on_connection_lost
        self.async_runner = AsyncRunner()
        self.pages = []
        self.current_page_index = -1
        self.sequences = {}
        self.current_project_path = None
        self.open_sequence_editors = {}
        self.is_project_dirty = False
        self.project_is_active = False

        self.clipboard_content = None
        self.clipboard_type = None
        
        self.reconnect_timer = QTimer(self)
        self.reconnect_timer.setInterval(5000)
        self.reconnect_timer.timeout.connect(self.attempt_reconnect)
        self.is_reconnecting = False
        
        # --- FEATURE: GLOBAL VARIABLES & ENGINE MANAGEMENT ---
        # The engine is now created on-demand for each run.
        # This dictionary holds all currently running sequence engines.
        self.running_sequences = {}
        # Central key-value store for the entire project.
        self.global_variables = {}

        self.setWindowTitle("NodeFlow")
        self.setWindowIcon(QIcon(resource_path("app/resources/icons/app_icon.ico")))
        
        main_container = QWidget()
        main_container_layout = QVBoxLayout(main_container)
        main_container_layout.setContentsMargins(0, 0, 0, 0)
        main_container_layout.setSpacing(0)
        
        self.title_bar = CustomTitleBar(self)
        main_container_layout.addWidget(self.title_bar)
        
        self.main_stack = QStackedWidget()
        main_container_layout.addWidget(self.main_stack)
        self.setCentralWidget(main_container)

        self.start_page = StartPage()
        self.start_page.new_project_requested.connect(self.new_project)
        self.start_page.open_project_requested.connect(self.open_project)
        self.start_page.open_recent_project_requested.connect(self.open_project)
        self.main_stack.addWidget(self.start_page)
        
        self.main_editor_widget = QWidget()
        main_layout = QVBoxLayout(self.main_editor_widget)
        
        self._create_menu_bar()
        
        self.tab_widget = QTabWidget()
        self.tab_widget.currentChanged.connect(self.on_main_tab_changed)
        main_layout.addWidget(self.tab_widget)
        self.main_stack.addWidget(self.main_editor_widget)

        self._create_dashboard_tab()
        self._create_sequencer_tab()
        self._create_docks()

        self.show_start_page()

        self.connection_success.connect(self.on_connection_success)
        self.connection_failed.connect(self.on_connection_failed)
        self.disconnection_finished.connect(self.on_disconnection_finished)
        
        self.widgets_pending_init = []
        
        # Set the initial status on the title bar when the window is created.
        self.title_bar.set_connection_status(False)

    def _get_resize_edge(self, pos: QPoint):
        """Checks if a given position is within the resize border."""
        top = pos.y() < self.border_thickness
        bottom = pos.y() > self.height() - self.border_thickness
        left = pos.x() < self.border_thickness
        right = pos.x() > self.width() - self.border_thickness

        edge = Qt.Edge(0)
        if top: edge |= Qt.Edge.TopEdge
        if bottom: edge |= Qt.Edge.BottomEdge
        if left: edge |= Qt.Edge.LeftEdge
        if right: edge |= Qt.Edge.RightEdge
        
        return edge

    def mousePressEvent(self, event):
        """Initiates a native window resize event when the border is clicked."""
        if event.button() == Qt.MouseButton.LeftButton:
            edge = self._get_resize_edge(event.pos())
            if edge:
                self.windowHandle().startSystemResize(edge)

    def mouseMoveEvent(self, event):
        """Updates the cursor shape when hovering over the window edges."""
        if self.isMaximized():
            return
            
        if event.buttons() == Qt.MouseButton.NoButton:
            edge = self._get_resize_edge(event.pos())
            if edge == (Qt.Edge.TopEdge | Qt.Edge.LeftEdge) or \
               edge == (Qt.Edge.BottomEdge | Qt.Edge.RightEdge):
                self.setCursor(Qt.CursorShape.SizeFDiagCursor)
            elif edge == (Qt.Edge.TopEdge | Qt.Edge.RightEdge) or \
                 edge == (Qt.Edge.BottomEdge | Qt.Edge.LeftEdge):
                self.setCursor(Qt.CursorShape.SizeBDiagCursor)
            elif edge == Qt.Edge.TopEdge or edge == Qt.Edge.BottomEdge:
                self.setCursor(Qt.CursorShape.SizeVerCursor)
            elif edge == Qt.Edge.LeftEdge or edge == Qt.Edge.RightEdge:
                self.setCursor(Qt.CursorShape.SizeHorCursor)
            else:
                self.setCursor(Qt.CursorShape.ArrowCursor)

    def set_project_dirty(self, dirty):
        if not self.project_is_active:
            return
        if self.is_project_dirty == dirty:
            return
        self.is_project_dirty = dirty
        self.update_window_title()

    def update_window_title(self):
        title = "NodeFlow"
        if self.project_is_active:
            if self.current_project_path:
                title += f" - {os.path.basename(self.current_project_path)}"
            else:
                title += " - New Project"
            
            if self.is_project_dirty:
                title += "*"
            
        self.title_bar.title_label.setText(title)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_F and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            if self.main_stack.currentWidget() is self.main_editor_widget:
                active_editor = self.get_current_sequence_editor()
                if active_editor:
                    if self.active_find_widget and self.active_find_widget.isVisible():
                        self.active_find_widget.hide()
                    active_editor.show_find_widget()
                    self.active_find_widget = active_editor.find_widget
                    def clear_active():
                        if self.active_find_widget == active_editor.find_widget:
                            self.active_find_widget = None
                    active_editor.find_widget.closed.connect(clear_active)
        else:
            super().keyPressEvent(event)
            
    def _create_docks(self):
        self._create_server_tree_dock()
        self._create_sequence_tree_dock()
        self._create_log_dock()

    def show_start_page(self):
        self.project_is_active = False
        self.is_project_dirty = False
        self.update_window_title()
        self.main_stack.setCurrentWidget(self.start_page)
        self.title_bar.menu_bar.hide()
        self.server_tree_dock.hide()
        self.sequence_tree_dock.hide()
        self.log_dock.hide()
        self.start_page.populate_recent_projects(self.get_recent_projects())
        
        self.setFixedSize(800, 600)
        screen_geometry = QApplication.primaryScreen().geometry()
        x = (screen_geometry.width() - self.width()) / 2
        y = (screen_geometry.height() - self.height()) / 2
        self.move(int(x), int(y))

    def show_main_editor(self):
        """Switches the view to the main editor and configures the UI."""
        self.setMinimumSize(QSize(0, 0))
        self.setMaximumSize(QSize(16777215, 16777215))

        self.main_stack.setCurrentWidget(self.main_editor_widget)
        self.title_bar.menu_bar.show()
        self.server_tree_dock.show()
        self.sequence_tree_dock.show()
        self.log_dock.show()
        
        screen_geometry = QApplication.primaryScreen().availableGeometry()
        self.setGeometry(screen_geometry)

    def add_to_recent_projects(self, file_path):
        settings = QSettings("MyCompany", "OPCUA-Client")
        recent_files = settings.value("recent_projects", [], type=list)
        if file_path in recent_files:
            recent_files.remove(file_path)
        recent_files.insert(0, file_path)
        settings.setValue("recent_projects", recent_files[:10])
        self._update_recent_projects_menu()

    def get_recent_projects(self):
        settings = QSettings("MyCompany", "OPCUA-Client")
        return settings.value("recent_projects", [], type=list)

    def new_project(self):
        if self.project_is_active and self.is_project_dirty:
            if not self.prompt_save_changes():
                return
        if self.opcua_logic.is_connected:
            self.async_runner.submit(self.disconnect())
        logging.info("Creating new project.")
        
        # --- FEATURE: GLOBAL VARIABLES ---
        self.global_variables.clear()
        
        self.clear_all_pages()
        self.close_all_sequence_tabs()
        self.sequences.clear()
        self.add_new_sequence("Default Sequence")
        self.open_sequence_in_tab("Default Sequence")
        self.current_project_path = None
        self.project_is_active = True
        self.set_project_dirty(False)
        self.update_window_title()
        self.show_main_editor()

    def open_project(self, file_path=None):
        if self.project_is_active and self.is_project_dirty:
            if not self.prompt_save_changes():
                return
        if not file_path:
            file_path, _ = QFileDialog.getOpenFileName(self, "Open Project", "", "Project Files (*.json)")
        if file_path:
            if self.opcua_logic.is_connected:
                self.async_runner.submit(self.disconnect())
            
            # --- FEATURE: GLOBAL VARIABLES ---
            self.global_variables.clear()

            self.clear_all_pages()
            self.close_all_sequence_tabs()
            try:
                with open(file_path, 'r') as f:
                    project_data = json.load(f)
                server_url = project_data.get('server_url', '')
                settings = QSettings("MyCompany", "OPCUA-Client")
                settings.setValue("server_url", server_url)
                dashboard_data = project_data.get('dashboard', [])
                for i, page_data in enumerate(dashboard_data):
                    if i > 0: self.add_new_page()
                    self.go_to_page(i)
                    for widget_data in page_data:
                        self.add_widget_to_dashboard(widget_data)
                sequences_data = project_data.get('sequences', {})
                self.sequences = sequences_data
                if not self.sequences:
                    self.add_new_sequence("Default Sequence")
                self._update_sequence_list()
                
                open_tabs = project_data.get('open_tabs', [])
                if open_tabs:
                    for tab_name in open_tabs:
                        if tab_name in self.sequences:
                            self.open_sequence_in_tab(tab_name)
                else:
                    first_sequence_name = next(iter(self.sequences), None)
                    if first_sequence_name:
                        self.open_sequence_in_tab(first_sequence_name)

                self.go_to_page(0)
                self.current_project_path = file_path
                logging.info(f"Project loaded from {file_path}")
                self.add_to_recent_projects(file_path)
                self.project_is_active = True
                self.set_project_dirty(False)
                self.update_window_title()
                self.show_main_editor()
                if server_url and not self.opcua_logic.is_connected:
                    logging.info(f"Project specifies server '{server_url}'. Connecting...")
                    self.toggle_connection()
            except Exception as e:
                logging.error(f"Failed to load project file: {e}")
                show_error_message("File Load Error", "The selected project file could not be loaded.", str(e))
                self.show_start_page()

    def save_project(self):
        if self.current_project_path:
            return self._save_to_path(self.current_project_path)
        else:
            return self.save_project_as()

    def save_project_as(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Project As", "", "Project Files (*.json)")
        if file_path:
            self.current_project_path = file_path
            return self._save_to_path(file_path)
        return False

    def _save_to_path(self, file_path):
        for name, editor in self.open_sequence_editors.items():
            if name in self.sequences:
                self.sequences[name] = editor.serialize()
        dashboard_data = []
        for page_widgets in self.pages:
            current_page_data = []
            for widget in page_widgets:
                current_page_data.append(widget.serialize())
            dashboard_data.append(current_page_data)
        settings = QSettings("MyCompany", "OPCUA-Client")
        server_url = settings.value("server_url", "")
        
        open_tabs = list(self.open_sequence_editors.keys())

        full_project_data = { 
            'server_url': server_url, 
            'dashboard': dashboard_data, 
            'sequences': self.sequences,
            'open_tabs': open_tabs
        }
        try:
            with open(file_path, 'w') as f:
                json.dump(full_project_data, f, indent=4)
            logging.info(f"Project saved to {file_path}")
            self.add_to_recent_projects(file_path)
            if server_url:
                settings.setValue(f"last_project_for_{server_url}", file_path)
            self.set_project_dirty(False)
            return True
        except Exception as e:
            logging.error(f"Failed to save project file: {e}")
            show_error_message("File Save Error", "The project could not be saved.", str(e))
            return False

    def prompt_save_changes(self):
        reply = QMessageBox.question(self, 'Unsaved Changes',
                                     "You have unsaved changes. Do you want to save them?",
                                     QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                                     QMessageBox.StandardButton.Save)

        if reply == QMessageBox.StandardButton.Save:
            return self.save_project()
        elif reply == QMessageBox.StandardButton.Discard:
            return True
        else: # Cancel
            return False

    def closeEvent(self, event):
        if self.project_is_active and self.is_project_dirty:
            if not self.prompt_save_changes():
                event.ignore()
                return

        logging.info("Close event accepted. Shutting down application...")
        self.reconnect_timer.stop()
        for page in self.pages:
            for widget in page:
                widget.stop_subscription()
        self.async_runner.submit(self.shutdown())
        event.accept()
    
    def _create_dashboard_tab(self):
        self.dashboard_container = QWidget()
        dashboard_layout = QVBoxLayout(self.dashboard_container)
        dashboard_layout.setContentsMargins(0, 0, 0, 0)

        # --- Alignment Toolbar ---
        self.alignment_toolbar = QToolBar("Alignment")
        self.align_left_action = self.alignment_toolbar.addAction("Align Left")
        self.align_center_action = self.alignment_toolbar.addAction("Align Center")
        self.align_right_action = self.alignment_toolbar.addAction("Align Right")
        self.align_top_action = self.alignment_toolbar.addAction("Align Top")
        self.align_middle_action = self.alignment_toolbar.addAction("Align Middle")
        self.align_bottom_action = self.alignment_toolbar.addAction("Align Bottom")
        self.alignment_toolbar.addSeparator()
        self.distribute_horizontal_action = self.alignment_toolbar.addAction("Distribute Horizontally")
        self.distribute_vertical_action = self.alignment_toolbar.addAction("Distribute Vertically")
        dashboard_layout.addWidget(self.alignment_toolbar)

        self.align_left_action.triggered.connect(lambda: self.align_widgets('left'))
        self.align_center_action.triggered.connect(lambda: self.align_widgets('center'))
        self.align_right_action.triggered.connect(lambda: self.align_widgets('right'))
        self.align_top_action.triggered.connect(lambda: self.align_widgets('top'))
        self.align_middle_action.triggered.connect(lambda: self.align_widgets('middle'))
        self.align_bottom_action.triggered.connect(lambda: self.align_widgets('bottom'))
        self.distribute_horizontal_action.triggered.connect(lambda: self.distribute_widgets('horizontal'))
        self.distribute_vertical_action.triggered.connect(lambda: self.distribute_widgets('vertical'))

        self.dashboard_area = QStackedWidget()
        dashboard_layout.addWidget(self.dashboard_area)
        dashboard_layout.addLayout(self._create_page_controls())
        self.tab_widget.addTab(self.dashboard_container, "Dashboard")
        self.add_new_page()

    def _create_sequencer_tab(self):
        self.sequencer_tab_container = QWidget()
        sequencer_tab_layout = QVBoxLayout(self.sequencer_tab_container)
        sequencer_tab_layout.setContentsMargins(2, 2, 2, 2)
        seq_manage_toolbar = QHBoxLayout()
        self.sequence_selector = QComboBox()
        open_seq_button = QPushButton("Open in Tab")
        open_seq_button.clicked.connect(self.open_selected_sequence_in_tab)
        new_seq_button = QPushButton("New")
        new_seq_button.clicked.connect(lambda: self.add_new_sequence(interactive=True))
        rename_seq_button = QPushButton("Rename")
        rename_seq_button.clicked.connect(self.rename_current_sequence)
        delete_seq_button = QPushButton("Delete")
        delete_seq_button.clicked.connect(self.delete_current_sequence)
        seq_manage_toolbar.addWidget(QLabel("Available Sequences:"))
        seq_manage_toolbar.addWidget(self.sequence_selector, 1)
        seq_manage_toolbar.addWidget(open_seq_button)
        seq_manage_toolbar.addWidget(new_seq_button)
        seq_manage_toolbar.addWidget(rename_seq_button)
        seq_manage_toolbar.addWidget(delete_seq_button)
        sequencer_tab_layout.addLayout(seq_manage_toolbar)
        self.sequence_tab_widget = QTabWidget()
        self.sequence_tab_widget.setTabsClosable(True)
        self.sequence_tab_widget.tabCloseRequested.connect(self.close_sequence_tab)
        self.sequence_tab_widget.currentChanged.connect(self.on_sequence_tab_changed)
        sequencer_tab_layout.addWidget(self.sequence_tab_widget)
        
        # --- MODIFIED TOOLBAR CONTAINER ---
        toolbar_container = QWidget()
        toolbar_container.setStyleSheet("""
            QWidget {
                background-color: #3c3f41;
                border: 1px solid #222;
                border-radius: 5px;
            }
        """)
        sequencer_toolbar = QHBoxLayout(toolbar_container)
        sequencer_toolbar.setContentsMargins(6, 6, 6, 6)

        # Create icon-based buttons
        self.run_button = QPushButton(QIcon(resource_path("app/resources/icons/play.png")), "")
        self.run_button.setToolTip("Run Sequence")

        self.stop_button = QPushButton(QIcon(resource_path("app/resources/icons/stop.png")), "")
        self.stop_button.setToolTip("Stop Execution")

        self.continue_button = QPushButton(QIcon(resource_path("app/resources/icons/continue.png")), "")
        self.continue_button.setToolTip("Continue / Resume")

        self.step_over_button = QPushButton(QIcon(resource_path("app/resources/icons/step_over.png")), "")
        self.step_over_button.setToolTip("Step Over")
        
        self.step_into_button = QPushButton(QIcon(resource_path("app/resources/icons/step_into.png")), "")
        self.step_into_button.setToolTip("Step Into")

        self.reset_button = QPushButton(QIcon(resource_path("app/resources/icons/reset.png")), "")
        self.reset_button.setToolTip("Reset Visual States")

        toolbar_buttons = [
            self.run_button, self.stop_button, self.continue_button, 
            self.step_over_button, self.step_into_button, self.reset_button
        ]
        for btn in toolbar_buttons:
            btn.setFixedSize(30, 30)
            btn.setIconSize(QSize(20, 20))
            btn.setStyleSheet("""
                QPushButton { border: 1px solid #555; border-radius: 4px; background-color: #2b2b2b; }
                QPushButton:hover { background-color: #4a4e52; }
                QPushButton:disabled { background-color: #2b2b2b; border: 1px solid #444; }
            """)

        # Add buttons to the layout
        sequencer_toolbar.addStretch()
        sequencer_toolbar.addWidget(self.run_button)
        sequencer_toolbar.addWidget(self.continue_button)
        sequencer_toolbar.addWidget(self.step_over_button)
        sequencer_toolbar.addWidget(self.step_into_button)
        sequencer_toolbar.addWidget(self.stop_button)
        sequencer_toolbar.addWidget(self.reset_button)
        sequencer_toolbar.addStretch()
        
        sequencer_tab_layout.addWidget(toolbar_container)
        
        # --- CORRECTED CONNECTIONS ---
        self.run_button.clicked.connect(self.on_run_button_clicked)
        self.stop_button.clicked.connect(self.on_stop_button_clicked)
        self.reset_button.clicked.connect(self.on_reset_button_clicked)
        self.continue_button.clicked.connect(self.on_continue_button_clicked)
        self.continue_button.setVisible(True) # Visibility will be managed by state
        self.step_over_button.clicked.connect(self.on_step_over_button_clicked)
        self.step_into_button.clicked.connect(self.on_step_into_button_clicked)
        
        self._set_idle_toolbar_state() # Set initial state
        
        self.tab_widget.addTab(self.sequencer_tab_container, "Sequencer")

    def _create_menu_bar(self):
        menu_bar = self.title_bar.menu_bar

        # --- File Menu ---
        file_menu = menu_bar.addMenu("File")
        file_menu.addAction("New Project", self.new_project)
        file_menu.addAction("Open Project...", self.open_project)
        self.open_recent_menu = file_menu.addMenu("Open Recent")
        self._update_recent_projects_menu()
        file_menu.addSeparator()
        
        save_action = QAction("Save", self)
        save_action.setShortcut(QKeySequence.StandardKey.Save)
        save_action.triggered.connect(self.save_project)
        file_menu.addAction(save_action)
        
        save_as_action = QAction("Save As...", self)
        save_as_action.setShortcut(QKeySequence.StandardKey.SaveAs)
        save_as_action.triggered.connect(self.save_project_as)
        file_menu.addAction(save_as_action)
        
        file_menu.addAction("Close Project", self.close_project)
        file_menu.addSeparator()
        file_menu.addAction("Exit", self.close)

        # --- Edit Menu ---
        self.edit_menu = menu_bar.addMenu("Edit")
        self.undo_action = QAction("Undo", self)
        self.redo_action = QAction("Redo", self)
        self.undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        self.redo_action.setShortcut(QKeySequence.StandardKey.Redo)
        self.edit_menu.addAction(self.undo_action)
        self.edit_menu.addAction(self.redo_action)
        self.edit_menu.addSeparator()
        
        cut_action = self.edit_menu.addAction("Cut")
        copy_action = self.edit_menu.addAction("Copy")
        paste_action = self.edit_menu.addAction("Paste")
        delete_action = self.edit_menu.addAction("Delete")
        
        cut_action.setShortcut(QKeySequence.StandardKey.Cut)
        copy_action.setShortcut(QKeySequence.StandardKey.Copy)
        paste_action.setShortcut(QKeySequence.StandardKey.Paste)
        delete_action.setShortcut(QKeySequence.StandardKey.Delete)

        cut_action.triggered.connect(self.cut_selection)
        copy_action.triggered.connect(self.copy_selection)
        paste_action.triggered.connect(self.paste_selection)
        delete_action.triggered.connect(self.delete_selection)
        
        self.edit_menu.addSeparator()
        self.select_all_action = self.edit_menu.addAction("Select All")
        self.select_all_action.setShortcut(QKeySequence.StandardKey.SelectAll)
        self.select_all_action.triggered.connect(self.select_all)
        self.edit_menu.addSeparator()
        
        find_action = QAction("Find in Project...", self)
        find_action.triggered.connect(self.open_global_find)
        self.edit_menu.addAction(find_action)

        # --- Connections Menu ---
        connections_menu = menu_bar.addMenu("Connections")
        self.toggle_connection_action = QAction("Connect", self)
        self.toggle_connection_action.triggered.connect(self.toggle_connection)
        connections_menu.addAction(self.toggle_connection_action)
        connections_menu.addSeparator()
        connections_menu.addAction("Server Settings...", self.open_server_settings_dialog)

        # --- View Menu ---
        view_menu = menu_bar.addMenu("View")
        
        zoom_in_action = view_menu.addAction("Zoom In")
        zoom_out_action = view_menu.addAction("Zoom Out")
        reset_zoom_action = view_menu.addAction("Reset Zoom")
        
        zoom_in_action.setShortcut(QKeySequence.StandardKey.ZoomIn)
        zoom_out_action.setShortcut(QKeySequence.StandardKey.ZoomOut)
        
        zoom_in_action.triggered.connect(lambda: self.get_current_sequence_editor().zoom_in() if self.get_current_sequence_editor() else None)
        zoom_out_action.triggered.connect(lambda: self.get_current_sequence_editor().zoom_out() if self.get_current_sequence_editor() else None)
        reset_zoom_action.triggered.connect(lambda: self.get_current_sequence_editor().reset_zoom() if self.get_current_sequence_editor() else None)
        
        view_menu.addSeparator()
        
        self.server_tree_dock = QDockWidget("Server Browser", self)
        self.sequence_tree_dock = QDockWidget("Sequence Library", self)
        self.log_dock = QDockWidget("Log", self)
        view_menu.addAction(self.server_tree_dock.toggleViewAction())
        view_menu.addAction(self.sequence_tree_dock.toggleViewAction())
        view_menu.addAction(self.log_dock.toggleViewAction())
        
        view_menu.addSeparator()
        
        switch_on_run_action = QAction("Switch to Sequencer on Run", self, checkable=True)
        settings = QSettings("MyCompany", "OPCUA-Client")
        switch_on_run_action.setChecked(settings.value("switch_on_run", True, type=bool))
        switch_on_run_action.toggled.connect(self.on_switch_on_run_toggled)
        view_menu.addAction(switch_on_run_action)

        theme_menu = view_menu.addMenu("Theme")
        light_theme_action = QAction("Light", self)
        dark_theme_action = QAction("Dark", self)
        light_theme_action.triggered.connect(lambda: self.apply_theme("Light"))
        dark_theme_action.triggered.connect(lambda: self.apply_theme("Dark"))
        theme_menu.addAction(light_theme_action)
        theme_menu.addAction(dark_theme_action)
    
    def on_switch_on_run_toggled(self, checked):
        settings = QSettings("MyCompany", "OPCUA-Client")
        settings.setValue("switch_on_run", checked)

    def toggle_full_screen(self):
        if self.isFullScreen():
            self.showMaximized()
        else:
            self.showFullScreen()
        
    def cut_selection(self):
        self.copy_selection()
        self.delete_selection()

    def copy_selection(self):
        if self.tab_widget.currentWidget() is self.sequencer_tab_container:
            active_editor = self.get_current_sequence_editor()
            if active_editor:
                self.clipboard_content = active_editor.get_selected_nodes_data()
                self.clipboard_type = 'sequencer'
                logging.info(f"Copied {len(self.clipboard_content)} nodes to clipboard.")
        elif self.tab_widget.currentWidget() is self.dashboard_container:
            selected_widgets = [w for w in self.pages[self.current_page_index] if w.isSelected()]
            if selected_widgets:
                self.clipboard_content = [w.serialize() for w in selected_widgets]
                self.clipboard_type = 'dashboard'
                logging.info(f"Copied {len(self.clipboard_content)} widgets to clipboard.")

    def paste_selection(self):
        if not self.clipboard_content:
            return

        if self.clipboard_type == 'sequencer' and self.tab_widget.currentWidget() is self.sequencer_tab_container:
            active_editor = self.get_current_sequence_editor()
            if active_editor:
                mouse_pos = active_editor.mapFromGlobal(QCursor.pos())
                scene_pos = active_editor.mapToScene(mouse_pos)
                active_editor.paste_nodes(self.clipboard_content, scene_pos)
        elif self.clipboard_type == 'dashboard' and self.tab_widget.currentWidget() is self.dashboard_container:
            for widget_data in self.clipboard_content:
                if 'geometry' in widget_data and widget_data['geometry']:
                        widget_data['geometry']['x'] += 20
                        widget_data['geometry']['y'] += 20
                self.add_widget_to_dashboard(widget_data)
        self.set_project_dirty(True)

    def delete_selection(self):
        items_deleted = False
        if self.tab_widget.currentWidget() is self.sequencer_tab_container:
            active_editor = self.get_current_sequence_editor()
            if active_editor:
                items_deleted = active_editor.delete_selected_items()
        elif self.tab_widget.currentWidget() is self.dashboard_container:
            selected_widgets = [w for w in self.pages[self.current_page_index] if w.isSelected()]
            if selected_widgets:
                items_deleted = True
                for widget in selected_widgets:
                    self.delete_widget(widget)
        if items_deleted:
            self.set_project_dirty(True)

    def align_widgets(self, edge):
        selected_widgets = [w for w in self.pages[self.current_page_index] if w.isSelected()]
        if len(selected_widgets) < 2:
            return

        # Use the first selected widget as the reference
        reference_widget = selected_widgets[0]
        ref_geom = reference_widget.geometry()

        for widget in selected_widgets[1:]:
            geom = widget.geometry()
            if edge == 'left':
                widget.move(ref_geom.left(), geom.y())
            elif edge == 'right':
                widget.move(ref_geom.right() - geom.width(), geom.y())
            elif edge == 'top':
                widget.move(geom.x(), ref_geom.top())
            elif edge == 'bottom':
                widget.move(geom.x(), ref_geom.bottom() - geom.height())
            elif edge == 'center':
                widget.move(ref_geom.center().x() - geom.width() // 2, geom.y())
            elif edge == 'middle':
                widget.move(geom.x(), ref_geom.center().y() - geom.height() // 2)
        self.set_project_dirty(True)

    def distribute_widgets(self, orientation):
        selected_widgets = [w for w in self.pages[self.current_page_index] if w.isSelected()]
        if len(selected_widgets) < 3:
            return

        if orientation == 'horizontal':
            selected_widgets.sort(key=lambda w: w.geometry().left())
            total_width = sum(w.width() for w in selected_widgets)
            min_x = selected_widgets[0].geometry().left()
            max_x = selected_widgets[-1].geometry().right()
            available_space = max_x - min_x - total_width
            spacing = available_space / (len(selected_widgets) - 1)

            current_x = min_x
            for widget in selected_widgets:
                widget.move(int(current_x), widget.y())
                current_x += widget.width() + spacing

        elif orientation == 'vertical':
            selected_widgets.sort(key=lambda w: w.geometry().top())
            total_height = sum(w.height() for w in selected_widgets)
            min_y = selected_widgets[0].geometry().top()
            max_y = selected_widgets[-1].geometry().bottom()
            available_space = max_y - min_y - total_height
            spacing = available_space / (len(selected_widgets) - 1)

            current_y = min_y
            for widget in selected_widgets:
                widget.move(widget.x(), int(current_y))
                current_y += widget.height() + spacing

        self.set_project_dirty(True)
        
    def open_global_find(self):
        if not self.sequences:
            show_info_message("Find", "There are no sequences in the current project to search.")
            return
            
        dialog = GlobalFindDialog(self.sequences, self)
        dialog.result_selected.connect(self.on_global_find_result)
        dialog.exec()

    def on_global_find_result(self, sequence_name, node_uuid):
        self.open_sequence_in_tab(sequence_name)
        
        QTimer.singleShot(50, lambda: self.highlight_node_in_editor(sequence_name, node_uuid))

    def highlight_node_in_editor(self, sequence_name, node_uuid):
        editor = self.open_sequence_editors.get(sequence_name)
        if editor:
            node = editor.scene.find_node_by_uuid(node_uuid)
            if node:
                editor.centerOn(node)
                node.highlight()

    def select_all(self):
        if self.tab_widget.currentWidget() is self.sequencer_tab_container:
            active_editor = self.get_current_sequence_editor()
            if active_editor:
                active_editor.select_all_nodes()
        elif self.tab_widget.currentWidget() is self.dashboard_container:
            current_page_widgets = self.pages[self.current_page_index]
            for widget in current_page_widgets:
                widget.setSelected(True)

    def _update_recent_projects_menu(self):
        self.open_recent_menu.clear()
        recent_files = self.get_recent_projects()
        if not recent_files:
            no_recent_action = QAction("No recent projects", self)
            no_recent_action.setEnabled(False)
            self.open_recent_menu.addAction(no_recent_action)
        else:
            for path in recent_files:
                action = QAction(os.path.basename(path), self)
                action.triggered.connect(lambda checked, p=path: self.open_project(p))
                self.open_recent_menu.addAction(action)

    def close_project(self):
        if self.project_is_active and self.is_project_dirty:
            if not self.prompt_save_changes():
                return
        if self.opcua_logic.is_connected:
            self.async_runner.submit(self.disconnect())
        
        self.current_project_path = None
        self.project_is_active = False
        self.title_bar.title_label.setText("NodeFlow")
        self.show_start_page()

    def _create_server_tree_dock(self):
        self.server_tree_dock.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        self.server_tree = ServerTreeView(self.opcua_logic, self.async_runner)
        self.server_tree.create_widget_requested.connect(self.on_create_widget_from_tree)
        self.server_tree.add_to_sequencer_requested.connect(self.add_node_to_current_sequencer)
        self.server_tree_dock.setWidget(self.server_tree)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.server_tree_dock)

    def _create_sequence_tree_dock(self):
        self.sequence_tree_dock.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        self.sequence_tree = SequenceTreeView()
        self.sequence_tree.create_sequence_widget_requested.connect(self.on_create_sequence_widget_from_tree)
        self.sequence_tree_dock.setWidget(self.sequence_tree)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.sequence_tree_dock)

    def _create_page_controls(self):
        nav_layout = QHBoxLayout()
        self.add_page_button = QPushButton("+ Add Page")
        self.add_page_button.clicked.connect(self.add_new_page)
        self.delete_page_button = QPushButton("Delete Page")
        self.delete_page_button.clicked.connect(self.delete_current_page)
        self.prev_page_button = QPushButton("<")
        self.prev_page_button.clicked.connect(self.prev_page)
        self.page_label = QLabel("Page 1 / 1")
        self.next_page_button = QPushButton(">")
        self.next_page_button.clicked.connect(self.next_page)
        nav_layout.addWidget(self.add_page_button)
        nav_layout.addWidget(self.delete_page_button)
        nav_layout.addStretch()
        nav_layout.addWidget(self.prev_page_button)
        nav_layout.addWidget(self.page_label)
        nav_layout.addWidget(self.next_page_button)
        return nav_layout

    def _create_log_dock(self):
        self.log_dock.setAllowedAreas(Qt.DockWidgetArea.BottomDockWidgetArea)
        self.log_widget = LogWidget()
        self.log_dock.setWidget(self.log_widget)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.log_dock)
        self.log_handler = QtLogHandler()
        self.log_handler.log_received.connect(self.log_widget.add_log_message)
        logging.getLogger().addHandler(self.log_handler)

    async def shutdown(self):
        if self.opcua_logic.is_connected:
            await self.disconnect()
        tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        logging.shutdown()
        QApplication.instance().quit()

    def toggle_connection(self):
        if self.opcua_logic.is_connected:
            self.async_runner.submit(self.disconnect())
        else:
            if not self.is_reconnecting:
                self.async_runner.submit(self.connect())

    async def connect(self):
        settings = QSettings("MyCompany", "OPCUA-Client")
        url = settings.value("server_url", "opc.tcp://localhost:4840/freeopcua/server/")
        auth_enabled = settings.value("auth_enabled", False, type=bool)
        username = settings.value("username", "") if auth_enabled else None
        password = settings.value("password", "") if auth_enabled else None
        
        logging.info(f"Attempting to connect to {url}...")
        try:
            await self.opcua_logic.connect(url, username, password)
            self.connection_success.emit()
        except Exception as e:
            logging.error(f"Connection failed: {e}")
            self.connection_failed.emit("Connection Failed", str(e))

    async def disconnect(self):
        self.reconnect_timer.stop()
        self.is_reconnecting = False
        logging.info("Manual disconnect initiated. Auto-reconnect disabled.")
        await self.opcua_logic.disconnect()
        self.disconnection_finished.emit()

    def on_connection_success(self):
        if self.is_reconnecting:
            self.reconnect_timer.stop()
            self.is_reconnecting = False
            logging.info("Successfully reconnected to server.")
        else:
            logging.info("Successfully connected to server.")
            
        for widget in getattr(self, 'widgets_pending_init', []):
            self.async_runner.submit(widget.initialize())
        self.widgets_pending_init.clear()
        
        self.toggle_connection_action.setText("Disconnect")
        self.server_tree.populate_root()
        
        # Update the title bar status indicator to green.
        self.title_bar.set_connection_status(True)
        
    def on_disconnection_finished(self):
        logging.info("Disconnected.")
        self.server_tree.clear()
        self.toggle_connection_action.setText("Connect")
        
        # Update the title bar status indicator to red.
        self.title_bar.set_connection_status(False)

    def on_connection_lost(self):
        if self.is_reconnecting:
            return
        logging.warning("Connection to OPC-UA server lost. Attempting to reconnect...")
        # FIX: Update the UI to show disconnected status immediately.
        self.title_bar.set_connection_status(False)
        self.is_reconnecting = True
        self.reconnect_timer.start()

    def attempt_reconnect(self):
        logging.info("Attempting to reconnect...")
        self.async_runner.submit(self.connect())

    def on_connection_failed(self, title, message):
        if not self.is_reconnecting:
            show_error_message(title, "Could not establish connection to the server.", message)
        else:
            logging.warning(f"Reconnect attempt failed: {message}")
        self.toggle_connection_action.setText("Connect")
        
        # Update the title bar status indicator to red.
        self.title_bar.set_connection_status(False)

    def open_add_widget_dialog(self, config_to_edit=None, is_from_tree=False):
        dialog = AddWidgetDialog(self, config_to_edit=config_to_edit, is_from_tree=is_from_tree)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        dialog.config_accepted.connect(self.handle_add_widget_dialog_accept)
        dialog.show()

    def handle_add_widget_dialog_accept(self, new_config):
        if new_config.get("widget_type") == "Sequence Button":
            if new_config.get("sequence_name"):
                widget_data = {"config": new_config}
                self.add_widget_to_dashboard(widget_data)
        elif new_config.get("identifier"):
            widget_data = {"config": new_config}
            self.add_widget_to_dashboard(widget_data)

    def on_create_widget_from_tree(self, partial_config):
        self.open_add_widget_dialog(config_to_edit=partial_config, is_from_tree=True)

    def on_create_sequence_widget_from_tree(self, sequence_name):
        config = { "widget_type": "Sequence Button", "label": f"Run: {sequence_name}", "sequence_name": sequence_name }
        self.add_widget_to_dashboard({"config": config})

    def add_widget_to_dashboard(self, widget_data):
        config = widget_data['config']
        geometry = widget_data.get('geometry')
        widget_type = config["widget_type"]
        widget_class_map = { "Numerical Display": DisplayWidget, "Text Display": DisplayWidget, "Switch": SwitchWidget, "String Input": InputWidget, "Numerical Input": InputWidget, "Button": ButtonWidget, "Sequence Button": SequenceWidget }
        widget_class = widget_class_map.get(widget_type)
        if not widget_class:
            logging.error(f"Unknown widget type '{widget_type}' in project file.")
            return
        current_grid = self.dashboard_area.widget(self.current_page_index)
        new_widget = widget_class(config, self.opcua_logic, current_grid, self.async_runner)
        
        if 'widget_state' in widget_data and hasattr(new_widget, 'restore_state'):
            new_widget.restore_state(widget_data['widget_state'])

        if isinstance(new_widget, SequenceWidget):
            new_widget.run_sequence_requested.connect(self.run_sequence_by_name)
            new_widget.stop_sequence_requested.connect(self.stop_sequence_loop)
        new_widget.request_delete.connect(self.delete_widget)
        new_widget.widget_changed.connect(lambda: self.set_project_dirty(True))
        self.pages[self.current_page_index].append(new_widget)
        if geometry:
            new_widget.move(geometry['x'], geometry['y'])
            new_widget.resize(geometry['width'], geometry['height'])
        else:
            offset = (len(self.pages[self.current_page_index]) % 10) * 20
            new_widget.move(10 + offset, 10 + offset)
        if widget_data.get("is_minimized"):
            original_size_data = widget_data.get("original_size")
            if original_size_data:
                new_widget._original_size = QSize(original_size_data['width'], original_size_data['height'])
            new_widget.toggle_minimize_state()
        new_widget.show()
        self.set_project_dirty(True)
        if not self.opcua_logic.is_connected:
            self.widgets_pending_init.append(new_widget)
        else:
            self.async_runner.submit(new_widget.initialize())
            
    def delete_widget(self, widget_to_delete, update_log=True):
        for page_widgets in self.pages:
            if widget_to_delete in page_widgets:
                widget_to_delete.stop_subscription()
                page_widgets.remove(widget_to_delete)
                widget_to_delete.setParent(None)
                widget_to_delete.deleteLater()
                if update_log:
                    logging.info(f"Deleted widget: {widget_to_delete.config.get('label', 'N/A')}")
                self.set_project_dirty(True)
                break

    def clear_all_pages(self):
        for page_widgets in self.pages:
            for widget in page_widgets[:]:
                self.delete_widget(widget, update_log=False)
        while self.dashboard_area.count() > 1:
            widget = self.dashboard_area.widget(1)
            self.dashboard_area.removeWidget(widget)
            widget.deleteLater()
        self.pages = [self.pages[0]] if self.pages else []
        if not self.pages:
            self.add_new_page()
        self.go_to_page(0)

    def add_new_page(self):
        new_page_grid = DashboardGrid()
        self.dashboard_area.addWidget(new_page_grid)
        self.pages.append([])
        self.go_to_page(len(self.pages) - 1)
        self.set_project_dirty(True)
        logging.info(f"Added new page. Total pages: {len(self.pages)}")

    def delete_current_page(self):
        if len(self.pages) <= 1:
            show_info_message("Action Blocked", "Cannot delete the last remaining page.")
            return
        page_to_delete_index = self.current_page_index
        widgets_on_page = self.pages[page_to_delete_index]
        if widgets_on_page:
            reply = QMessageBox.question(self, 'Confirm Deletion', "This page contains widgets. Are you sure you want to delete it?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.No:
                return
        logging.info(f"Deleting page {page_to_delete_index + 1}...")
        for widget in widgets_on_page[:]:
            self.delete_widget(widget, update_log=False)
        page_widget = self.dashboard_area.widget(page_to_delete_index)
        self.dashboard_area.removeWidget(page_widget)
        page_widget.deleteLater()
        del self.pages[page_to_delete_index]
        new_index = max(0, page_to_delete_index - 1)
        self.go_to_page(new_index)
        self.set_project_dirty(True)
        logging.info(f"Page deleted. Now on page {new_index + 1}.")

    def go_to_page(self, page_index):
        if 0 <= page_index < len(self.pages):
            self.current_page_index = page_index
            self.dashboard_area.setCurrentIndex(page_index)
            self.update_page_ui()

    def next_page(self):
        self.go_to_page(self.current_page_index + 1)

    def prev_page(self):
        self.go_to_page(self.current_page_index - 1)

    def update_page_ui(self):
        self.page_label.setText(f"Page {self.current_page_index + 1} / {len(self.pages)}")
        self.prev_page_button.setEnabled(self.current_page_index > 0)
        self.next_page_button.setEnabled(self.current_page_index < len(self.pages) - 1)
        self.delete_page_button.setEnabled(len(self.pages) > 1)

    def toggle_delete_mode(self, checked):
        current_tab = self.tab_widget.currentWidget()
        if current_tab is self.dashboard_container:
            active_editor = self.get_current_sequence_editor()
            if active_editor: active_editor.set_delete_mode(False)
            for page in self.pages:
                for widget in page:
                    widget.set_delete_mode(checked)
        elif current_tab is self.sequencer_tab_container:
            for page in self.pages:
                for widget in page:
                    widget.set_delete_mode(False)
            active_editor = self.get_current_sequence_editor()
            if active_editor: active_editor.set_delete_mode(checked)
        if not checked:
            active_editor = self.get_current_sequence_editor()
            if active_editor: active_editor.set_delete_mode(False)
            for page in self.pages:
                for widget in page:
                    widget.set_delete_mode(False)

    def _update_sequence_list(self):
        try:
            sequence_names = [str(key) for key in self.sequences.keys()]
        except Exception as e:
            logging.error(f"Could not convert sequence keys to strings: {e}")
            sequence_names = []
        self.sequence_tree.update_sequences(sequence_names)
        self.sequence_selector.blockSignals(True)
        current_text = self.sequence_selector.currentText()
        self.sequence_selector.clear()
        if sequence_names:
            self.sequence_selector.addItems(sequence_names)
        index = self.sequence_selector.findText(current_text)
        if index != -1:
            self.sequence_selector.setCurrentIndex(index)
        elif sequence_names:
            self.sequence_selector.setCurrentIndex(0)
        active_editor = self.get_current_sequence_editor()
        if active_editor:
            active_editor.set_available_sequences(sequence_names, self.get_current_sequence_name())
        self.sequence_selector.blockSignals(False)

    def add_new_sequence(self, name=None, interactive=False):
        if interactive:
            name, ok = QInputDialog.getText(self, "New Sequence", "Enter sequence name:")
            if not ok or not name.strip():
                return
            name = name.strip()
        if name in self.sequences:
            if interactive:
                show_error_message("Error", f"A sequence named '{name}' already exists.")
            return
        self.sequences[name] = {'nodes': [], 'exec_connections': [], 'data_connections': []}
        self._update_sequence_list()
        self.sequence_selector.setCurrentText(name)
        self.set_project_dirty(True)
        if interactive:
            self.open_sequence_in_tab(name)

    def rename_current_sequence(self):
        old_name = self.get_current_sequence_name()
        if not old_name: return
        new_name, ok = QInputDialog.getText(self, "Rename Sequence", "Enter new name:", text=old_name)
        if not ok or not new_name.strip() or new_name.strip() == old_name:
            return
        new_name = new_name.strip()
        if new_name in self.sequences:
            show_error_message("Error", f"A sequence named '{new_name}' already exists.")
            return
        self.sequences[new_name] = self.sequences.pop(old_name)
        if old_name in self.open_sequence_editors:
            editor = self.open_sequence_editors.pop(old_name)
            self.open_sequence_editors[new_name] = editor
            for i in range(self.sequence_tab_widget.count()):
                if self.sequence_tab_widget.tabText(i) == old_name:
                    self.sequence_tab_widget.setTabText(i, new_name)
                    break
        self._update_sequence_list()
        self.sequence_selector.setCurrentText(new_name)
        self.set_project_dirty(True)

    def delete_current_sequence(self):
        name = self.get_current_sequence_name()
        if not name or len(self.sequences) <= 1:
            show_info_message("Action Blocked", "Cannot delete the last sequence.")
            return
        reply = QMessageBox.question(self, 'Confirm Deletion', f"Are you sure you want to permanently delete the sequence '{name}'?")
        if reply == QMessageBox.StandardButton.Yes:
            if name in self.open_sequence_editors:
                for i in range(self.sequence_tab_widget.count()):
                    if self.sequence_tab_widget.tabText(i) == name:
                        self.close_sequence_tab(i)
                        break
            del self.sequences[name]
            self._update_sequence_list()
            self.set_project_dirty(True)

    def run_sequence_by_name(self, name, is_loop):
        if name in self.running_sequences:
            show_error_message("Already Running", f"Sequence '{name}' is already running.")
            return

        active_editor = self.open_sequence_editors.get(name)
        if active_editor:
            data = active_editor.serialize()
            self.sequences[name] = data # Ensure latest version is saved
        elif name in self.sequences:
            data = self.sequences[name]
        else:
            show_error_message("Not Found", f"Could not find sequence '{name}'.")
            return
            
        settings = QSettings("MyCompany", "OPCUA-Client")
        if settings.value("switch_on_run", True, type=bool):
            self.open_sequence_in_tab(name)
            self.tab_widget.setCurrentWidget(self.sequencer_tab_container)
        
        # --- Create a new engine for this run ---
        engine = SequenceEngine(self.opcua_logic, self.async_runner, self.global_variables)
        engine.execution_finished.connect(self.on_sequence_finished)

        # Connect UI update signals
        engine.node_state_changed.connect(self.on_node_state_changed)
        engine.connection_state_changed.connect(self.on_connection_state_changed)
        engine.execution_paused.connect(self.on_sequence_paused)

        self.running_sequences[name] = engine
        
        # Update dashboard widgets
        for page in self.pages:
            for widget in page:
                if isinstance(widget, SequenceWidget) and widget.sequence_name == name:
                    widget.set_running_state(True, is_loop)
        
        engine.run(name, self.sequences, loop=is_loop)
        logging.info(f"Started sequence '{name}' (Loop: {is_loop})")
        self._set_running_toolbar_state()

    def stop_sequence_loop(self, name):
        if name in self.running_sequences:
            engine = self.running_sequences[name]
            engine.stop()
            logging.info(f"Stopping sequence '{name}' from widget request.")
        else:
            logging.warning(f"Attempted to stop sequence '{name}' from widget, but it was not running.")

    def on_run_button_clicked(self):
        self.on_reset_button_clicked()
        current_name = self.get_current_sequence_name()
        if current_name:
            self.run_sequence_by_name(current_name, is_loop=False)

    def on_stop_button_clicked(self):
        # Stop all running sequences for simplicity, or just the current one
        current_name = self.get_current_sequence_name()
        if current_name and current_name in self.running_sequences:
            logging.info(f"Stop button clicked for sequence '{current_name}'.")
            self.running_sequences[current_name].stop()
        else:
            # If current tab isn't running, stop the first one found (e.g. from a widget)
            if self.running_sequences:
                first_running_name = next(iter(self.running_sequences))
                logging.info(f"Stop button clicked. Stopping first active sequence '{first_running_name}'.")
                self.running_sequences[first_running_name].stop()

    def on_reset_button_clicked(self):
        logging.info("Reset button clicked.")
        for editor in self.open_sequence_editors.values():
            editor.reset_visual_states()
            
    def on_sequence_finished(self, sequence_name, status_message):
        if sequence_name in self.running_sequences:
            del self.running_sequences[sequence_name]
            logging.info(f"Sequence '{sequence_name}' finished: {status_message}")

        # Update dashboard widgets
        for page in self.pages:
            for widget in page:
                if isinstance(widget, SequenceWidget) and widget.sequence_name == sequence_name:
                    widget.set_running_state(False)
        
        # If no other sequences are running, reset the toolbar
        if not self.running_sequences:
            self._set_idle_toolbar_state()

    def _set_idle_toolbar_state(self):
        """Helper to set toolbar buttons for the idle state."""
        self.run_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.continue_button.setEnabled(False)
        self.step_over_button.setEnabled(False)
        self.step_into_button.setEnabled(False)
        self.reset_button.setEnabled(True)

    def _set_running_toolbar_state(self):
        """Helper to set toolbar buttons for an active, non-paused run."""
        self.run_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.continue_button.setEnabled(False)
        self.step_over_button.setEnabled(False)
        self.step_into_button.setEnabled(False)
        self.reset_button.setEnabled(False)

    def _set_paused_toolbar_state(self):
        """Helper to set toolbar buttons for the paused/breakpoint state."""
        self.run_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.continue_button.setEnabled(True)
        self.step_over_button.setEnabled(True)
        self.step_into_button.setEnabled(True)
        self.reset_button.setEnabled(False)

    def on_continue_button_clicked(self):
        current_name = self.get_current_sequence_name()
        if current_name and current_name in self.running_sequences:
            engine = self.running_sequences[current_name]
            if engine.is_paused:
                engine.resume()
                self._set_running_toolbar_state()

    def on_step_over_button_clicked(self):
        # This functionality depends on the new SequenceEngine
        show_info_message("Not Implemented", "Step Over functionality is not yet implemented.")

    def on_step_into_button_clicked(self):
        # This functionality depends on the new SequenceEngine
        show_info_message("Not Implemented", "Step Into functionality is not yet implemented.")
    
    def on_sequence_paused(self, sequence_name, node_uuid):
        """Called when the engine hits a breakpoint."""
        logging.info(f"Execution paused at node {node_uuid} in sequence {sequence_name}")
        self._set_paused_toolbar_state()
        
        editor = self.open_sequence_editors.get(sequence_name)
        if editor:
            editor.update_node_state(node_uuid, "paused")
            node = editor.scene.find_node_by_uuid(node_uuid)
            if node:
                editor.centerOn(node)

    def on_node_state_changed(self, sequence_name, node_uuid, state):
        editor = self.open_sequence_editors.get(sequence_name)
        if editor:
            editor.update_node_state(node_uuid, state)

    def on_connection_state_changed(self, sequence_name, start_uuid, end_uuid, state):
        editor = self.open_sequence_editors.get(sequence_name)
        if editor:
            editor.update_connection_state(start_uuid, end_uuid, state)

    def open_server_settings_dialog(self):
        dialog = ServerSettingsDialog(self)
        dialog.exec()

    def apply_theme(self, theme_name):
        style_sheet = ""
        try:
            filename = resource_path(f"app/resources/styles/{theme_name.lower()}_theme.qss")
            with open(filename, "r") as f:
                style_sheet = f.read()
            logging.info(f"Loaded theme: {theme_name}")
        except FileNotFoundError:
            logging.error(f"Could not find stylesheet for theme: {theme_name} at '{filename}'")
        QApplication.instance().setStyleSheet(style_sheet)

    def get_current_sequence_editor(self):
        current_widget = self.sequence_tab_widget.currentWidget()
        if isinstance(current_widget, SequenceEditor):
            return current_widget
        return None

    def get_current_sequence_name(self):
        index = self.sequence_tab_widget.currentIndex()
        if index != -1:
            return self.sequence_tab_widget.tabText(index)
        return None

    def open_selected_sequence_in_tab(self):
        sequence_name = self.sequence_selector.currentText()
        if sequence_name:
            self.open_sequence_in_tab(sequence_name)

    def open_sequence_in_tab(self, name):
        if name in self.open_sequence_editors:
            widget = self.open_sequence_editors[name]
            self.sequence_tab_widget.setCurrentWidget(widget)
            return
        if name not in self.sequences:
            logging.error(f"Attempted to open non-existent sequence '{name}' in a tab.")
            return
        editor = SequenceEditor(self)
        editor.load_data(self.sequences[name])
        index = self.sequence_tab_widget.addTab(editor, name)
        self.sequence_tab_widget.setCurrentIndex(index)
        self.open_sequence_editors[name] = editor
        self.on_sequence_tab_changed(index)

    def close_sequence_tab(self, index):
        name = self.sequence_tab_widget.tabText(index)
        if name in self.open_sequence_editors:
            editor = self.open_sequence_editors[name]
            self.sequences[name] = editor.serialize()
            editor.deleteLater()
            del self.open_sequence_editors[name]
        self.sequence_tab_widget.removeTab(index)

    def close_all_sequence_tabs(self):
        for i in range(self.sequence_tab_widget.count() -1, -1, -1):
            self.close_sequence_tab(i)
        self.open_sequence_editors.clear()

    def on_sequence_clean_changed(self, is_clean):
        if not is_clean:
            self.set_project_dirty(True)

    def on_sequence_tab_changed(self, index):
        active_editor = self.get_current_sequence_editor()
        if active_editor:
            try:
                active_editor.scene_changed.disconnect(self._on_scene_changed)
            except (TypeError, RuntimeError):
                pass # Ignore if not connected
            active_editor.scene_changed.connect(self._on_scene_changed)
            try:
                self.undo_action.triggered.disconnect()
                self.redo_action.triggered.disconnect()
                for editor in self.open_sequence_editors.values():
                    try:
                        editor.scene.undo_stack.cleanChanged.disconnect(self.on_sequence_clean_changed)
                    except (TypeError, RuntimeError):
                        pass
            except TypeError:
                pass 
            new_undo_action = active_editor.scene.undo_stack.createUndoAction(self)
            new_redo_action = active_editor.scene.undo_stack.createRedoAction(self)
            
            new_undo_action.setText("Undo")
            new_redo_action.setText("Redo")
            
            new_undo_action.setShortcut(QKeySequence.StandardKey.Undo)
            new_redo_action.setShortcut(QKeySequence.StandardKey.Redo)

            self.edit_menu.insertAction(self.undo_action, new_undo_action)
            self.edit_menu.removeAction(self.undo_action)
            self.undo_action.deleteLater()
            self.undo_action = new_undo_action

            self.edit_menu.insertAction(self.redo_action, new_redo_action)
            self.edit_menu.removeAction(self.redo_action)
            self.redo_action.deleteLater()
            self.redo_action = new_redo_action
            
            active_editor.scene.undo_stack.cleanChanged.connect(self.on_sequence_clean_changed)
            
            sequence_names = list(self.sequences.keys())
            active_editor.set_available_sequences(sequence_names, self.get_current_sequence_name())
                
    def add_node_to_current_sequencer(self, config):
        active_editor = self.get_current_sequence_editor()
        if active_editor:
            active_editor.add_node(config)
        else:
            show_info_message("Action Failed", "Cannot add node. No sequence is currently open in a tab.")
            
    def _on_scene_changed(self):
        self.set_project_dirty(True)

    def on_main_tab_changed(self, index):
        is_dashboard = self.tab_widget.widget(index) == self.dashboard_container
        self.alignment_toolbar.setVisible(is_dashboard)