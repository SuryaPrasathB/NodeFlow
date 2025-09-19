from PyQt6.QtWidgets import QPushButton, QVBoxLayout, QMenu, QLabel
from PyQt6.QtGui import QAction
from PyQt6.QtCore import pyqtSignal, Qt
from .base_widget import BaseWidget

class SequenceWidget(BaseWidget):
    """
    A dashboard widget to control a pre-defined sequence.

    This widget acts as a remote control for a sequence created in the
    Sequencer Editor. It can start the sequence for a single run or in a
    continuous loop, and can stop a running sequence. It communicates its
    intentions to the main window via signals.

    Attributes:
        run_sequence_requested (pyqtSignal): Emitted to request a sequence run.
                                             Passes sequence_name (str) and loop (bool).
        stop_sequence_requested (pyqtSignal): Emitted to request a sequence stop.
                                              Passes sequence_name (str).
    """
    run_sequence_requested = pyqtSignal(str, bool)
    stop_sequence_requested = pyqtSignal(str)
    widget_changed = pyqtSignal()

    def __init__(self, config, opcua_logic, parent=None, async_runner=None):
        """
        Initializes the SequenceWidget.

        Args:
            config (dict): The configuration dictionary for the widget.
            opcua_logic (OpcuaClientLogic): The OPC UA logic instance.
            parent (QWidget, optional): The parent widget. Defaults to None.
            async_runner (AsyncRunner, optional): The runner for async tasks. Defaults to None.
        """
        super().__init__(config, opcua_logic, parent, async_runner)
        
        self.sequence_name = config.get('sequence_name', 'N/A')
        
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
        """
        Finalizes widget setup. For this widget, it just sets a ready status
        as it does not directly connect to an OPC UA node.
        """
        self.status_label.setText(f"Ready to run sequence.")
        self.node = True

    def on_run_clicked(self):
        """
        Handles the main button click, acting as a toggle.

        If the sequence is running, it emits a stop request. If not, it emits
        a request to run the sequence once.
        """
        if self.is_running:
            self.stop_sequence_requested.emit(self.sequence_name)
        else:
            # Default click action is still to run once.
            self.run_sequence_requested.emit(self.sequence_name, False)

    def set_running_state(self, is_running, is_looping=False):
        """
        Updates the widget's UI to reflect the current state of the sequence.

        This is a public method intended to be called by the main window, which
        manages the actual sequence execution.

        Args:
            is_running (bool): True if the sequence is currently running.
            is_looping (bool, optional): True if the sequence is in loop mode.
        """
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
        """
        Creates and displays a dynamic right-click context menu.

        If the sequence is running, it shows a 'Stop' action. If idle, it shows
        'Run Once' and 'Run in Loop' actions. It also includes standard options
        for minimizing or maximizing the widget.

        Args:
            event (QContextMenuEvent): The context menu event.
        """
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
