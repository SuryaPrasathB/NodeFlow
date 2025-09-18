from PyQt6.QtWidgets import QPushButton, QVBoxLayout, QMenu, QLabel
from PyQt6.QtGui import QAction
from PyQt6.QtCore import pyqtSignal, Qt
from .base_widget import BaseWidget

class SequenceWidget(BaseWidget):
    """
    A button widget on the dashboard that can trigger a named sequence
    either once or in a continuous loop, and can also stop it.
    """
    run_sequence_requested = pyqtSignal(str, bool)
    stop_sequence_requested = pyqtSignal(str)
    # FIX: Explicitly define the signal here to resolve the AttributeError.
    # Even though it's in the parent, adding it here makes it discoverable.
    widget_changed = pyqtSignal()

    def __init__(self, config, opcua_logic, parent=None, async_runner=None):
        super().__init__(config, opcua_logic, parent, async_runner)
        
        self.sequence_name = config.get('sequence_name', 'N/A')
        
        ## UX REFINEMENT ##
        # This state now tracks if the sequence is running at all (loop or once)
        self.is_running = False

        # --- Standard View ---
        self.run_button = QPushButton(f"Run: {self.sequence_name}")
        font = self.run_button.font()
        font.setPointSize(12)
        self.run_button.setFont(font)
        
        self.loop_status_label = QLabel("State: Idle")
        self.loop_status_label.setStyleSheet("font-size: 9pt; color: gray;")
        
        self.content_area_layout.addWidget(self.run_button)
        self.content_area_layout.addWidget(self.loop_status_label)
        self.run_button.clicked.connect(self.on_run_clicked)
        
        # --- Minimized View ---
        minimized_layout = QVBoxLayout(self.minimized_widget)
        minimized_layout.setContentsMargins(5, 5, 5, 5)
        self.minimized_button = QPushButton(self.sequence_name)
        self.minimized_button.setStyleSheet("font-size: 11pt;")
        minimized_layout.addWidget(self.minimized_button)
        self.minimized_button.clicked.connect(self.on_run_clicked)
        self.minimized_widget.setStyleSheet("""
            #minimizedWidget {
                background-color: #3c3f41; border: 1px solid #555; border-radius: 4px;
            }
        """)

    async def setup_widget(self):
        self.status_label.setText(f"Ready to run sequence.")
        self.node = True

    ## UX REFINEMENT ##
    # The button click is now a toggle for running or stopping the sequence.
    def on_run_clicked(self):
        if self.is_running:
            self.stop_sequence_requested.emit(self.sequence_name)
        else:
            # Default click action is still to run once.
            self.run_sequence_requested.emit(self.sequence_name, False)

    ## UX REFINEMENT ##
    # Renamed and enhanced to handle all running states.
    def set_running_state(self, is_running, is_looping=False):
        """Public method for MainWindow to update this widget's UI."""
        self.is_running = is_running
        if self.is_running:
            state_text = "Running in Loop..." if is_looping else "Running (Once)..."
            self.loop_status_label.setText(f"<font color='#f0e68c'>State: {state_text}</font>")
            self.run_button.setText("Stop Sequence")
            self.minimized_button.setText("Stop")
            # Style the button to indicate it's an active "stop" button
            self.run_button.setStyleSheet("background-color: #ff6347;")
            self.minimized_button.setStyleSheet("background-color: #ff6347; font-size: 11pt;")
        else:
            self.loop_status_label.setText("State: Idle")
            self.run_button.setText(f"Run: {self.sequence_name}")
            self.minimized_button.setText(self.sequence_name)
            # Reset style
            self.run_button.setStyleSheet("")
            self.minimized_button.setStyleSheet("font-size: 11pt;")

    def contextMenuEvent(self, event):
        context_menu = QMenu(self)
        
        # If running, the only option is to stop.
        if self.is_running:
            stop_action = QAction("Stop Sequence", self)
            stop_action.triggered.connect(lambda: self.stop_sequence_requested.emit(self.sequence_name))
            context_menu.addAction(stop_action)
        else:
            run_once_action = QAction("Run Once", self)
            run_once_action.triggered.connect(lambda: self.run_sequence_requested.emit(self.sequence_name, False))
            context_menu.addAction(run_once_action)

            run_loop_action = QAction("Run in Loop", self)
            run_loop_action.triggered.connect(lambda: self.run_sequence_requested.emit(self.sequence_name, True))
            context_menu.addAction(run_loop_action)

        context_menu.addSeparator()
        
        if self.is_minimized:
            maximize_action = QAction("Maximize", self)
            maximize_action.triggered.connect(self.toggle_minimize_state)
            context_menu.addAction(maximize_action)
        else:
            minimize_action = QAction("Minimize", self)
            minimize_action.triggered.connect(self.toggle_minimize_state)
            context_menu.addAction(minimize_action)
        
        context_menu.exec(event.globalPos())
