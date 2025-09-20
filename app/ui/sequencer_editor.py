"""
Graphical Node-Based Editor for Creating Automation Sequences.

This module contains all the components required for the sequencer UI, including:
- SequenceEngine: The backend logic for executing the sequence graph.
- SequenceNode, Port, Connection: The QGraphicsObject classes that represent
  the visual elements of the sequence.
- SequenceScene, SequenceEditor: The QGraphicsScene and QGraphicsView that
  host and manage the interactive editor.
- Various dialogs for configuring nodes and connections.
"""
import logging
import asyncio
import uuid
from enum import Enum
from PyQt6.QtWidgets import (QGraphicsView, QGraphicsScene, QGraphicsObject, QGraphicsTextItem,
                             QStyleOptionGraphicsItem, QWidget, QGraphicsPathItem, QStyle,
                             QInputDialog, QLineEdit, QDialog, QFormLayout, QDialogButtonBox, QVBoxLayout, QMenu,
                             QComboBox, QGraphicsProxyWidget, QToolTip, QColorDialog, QPushButton, QTextEdit, QMessageBox, QLabel, QHBoxLayout, QRadioButton, QButtonGroup)
from PyQt6.QtCore import Qt, QRectF, QPointF, pyqtSignal, QObject, QPropertyAnimation
from PyQt6.QtGui import (QPainter, QColor, QBrush, QPen, QPainterPath, QKeyEvent,
                         QPainterPathStroker, QUndoCommand, QUndoStack, QFont, QTransform, QAction, QIcon)

# --- Local Imports ---
from .condition_dialog import ConditionDialog
from .node_config_dialog import NodeConfigDialog
from .compute_node_dialog import ComputeNodeDialog
from .error_dialog import show_error_message
from app.ui.widgets.find_widget import FindWidget
from app.utils.paths import resource_path
from .python_script_dialog import PythonScriptDialog
from app.core.mysql_manager import MySQLManager
from PyQt6.QtCore import QSettings

class VariableNodeDialog(QDialog):
    """A dialog for configuring Set/Get Variable nodes."""
    def __init__(self, parent=None, current_config=None, available_variables=None):
        super().__init__(parent)
        self.setWindowTitle("Configure Variable Node")
        self.config = current_config or {}

        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        self.variable_combo = QComboBox()
        if available_variables:
            self.variable_combo.addItems(available_variables)

        form_layout.addRow("Variable Name:", self.variable_combo)
        layout.addLayout(form_layout)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        if self.config.get('variable_name'):
            self.variable_combo.setCurrentText(self.config['variable_name'])

    def get_config(self):
        """Retrieves the updated configuration from the dialog."""
        selected_variable = self.variable_combo.currentText()
        if not selected_variable:
            show_error_message("Configuration Error", "You must select a variable.")
            return None

        self.config['variable_name'] = selected_variable
        node_type = self.config.get('node_type', 'Variable')
        self.config['label'] = f"{node_type}: {selected_variable}"
        return self.config

class MySQLReadNodeDialog(QDialog):
    """A dialog for configuring the MySQL Read Node."""
    def __init__(self, parent=None, current_config=None):
        super().__init__(parent)
        self.setWindowTitle("Configure MySQL Read Node")
        self.config = current_config or {}
        self.setMinimumWidth(400)

        self.layout = QVBoxLayout(self)
        self.form_layout = QFormLayout()

        self.query_input = QTextEdit(self.config.get('query', ''))
        self.form_layout.addRow(QLabel("SELECT Query:"), self.query_input)

        self.layout.addLayout(self.form_layout)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        self.layout.addWidget(button_box)

    def get_config(self):
        self.config['query'] = self.query_input.toPlainText()
        self.config['label'] = f"Read: {self.config['query'][:20]}..."
        return self.config

class MySQLWriteNodeDialog(QDialog):
    """A dialog for configuring the MySQL Write Node."""
    def __init__(self, parent=None, current_config=None):
        super().__init__(parent)
        self.setWindowTitle("Configure MySQL Write Node")
        self.config = current_config or {}
        self.setMinimumWidth(450)

        # UI Elements
        self.layout = QVBoxLayout(self)
        self.form_layout = QFormLayout()

        self.table_name_combo = QComboBox()
        self.table_name_combo.setEditable(True)
        self.table_name_combo.currentIndexChanged.connect(self.refresh_columns)
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh_tables_and_columns)

        self.form_layout.addRow(QLabel("Table Name:"), self.table_name_combo)
        self.form_layout.addRow(self.refresh_button)

        self.mappings_layout = QVBoxLayout()
        self.input_widgets = {}
        self.key_button_group = QButtonGroup()

        self.add_input_button = QPushButton("Add Input Socket")
        self.add_input_button.clicked.connect(self.add_input_socket)

        self.layout.addLayout(self.form_layout)
        self.layout.addLayout(self.mappings_layout)
        self.layout.addWidget(self.add_input_button)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        self.layout.addWidget(button_box)

        self.available_columns = []
        self.populate_inputs()
        self.refresh_tables_and_columns()

    def populate_inputs(self):
        for i in reversed(range(self.mappings_layout.count())):
            widget_item = self.mappings_layout.itemAt(i)
            if widget_item and widget_item.widget():
                widget_item.widget().setParent(None)
        self.input_widgets.clear()
        # Clear the button group before repopulating
        for button in self.key_button_group.buttons():
            self.key_button_group.removeButton(button)

        inputs = self.config.get('inputs', [])
        for input_name in inputs:
            self.add_mapping_widget(input_name)

    def add_mapping_widget(self, input_name):
        h_layout = QHBoxLayout()
        label = QLineEdit(input_name)
        label.setPlaceholderText("Input Socket Name")
        combo = QComboBox()
        combo.addItems(self.available_columns)

        current_mapping = self.config.get('mappings', {}).get(input_name)
        if current_mapping in self.available_columns:
            combo.setCurrentText(current_mapping)

        radio_button = QRadioButton("Key")
        self.key_button_group.addButton(radio_button)
        if self.config.get('unique_key_input') == input_name:
            radio_button.setChecked(True)

        remove_button = QPushButton("X")
        remove_button.setFixedWidth(30)
        remove_button.clicked.connect(lambda _, name=input_name: self.remove_input_socket(name))

        h_layout.addWidget(QLabel("Input:"))
        h_layout.addWidget(label)
        h_layout.addWidget(QLabel("-> Column:"))
        h_layout.addWidget(combo)
        h_layout.addWidget(radio_button)
        h_layout.addWidget(remove_button)

        container_widget = QWidget()
        container_widget.setLayout(h_layout)
        self.mappings_layout.addWidget(container_widget)

        self.input_widgets[input_name] = {'label_widget': label, 'combo': combo, 'radio': radio_button, 'layout_widget': container_widget}

    def add_input_socket(self):
        input_name, ok = QInputDialog.getText(self, "Add Input", "Enter new input socket name:")
        if ok and input_name:
            if input_name not in self.config.get('inputs', []):
                self.config.setdefault('inputs', []).append(input_name)
                self.add_mapping_widget(input_name)

    def remove_input_socket(self, input_name):
        if input_name in self.config.get('inputs', []):
            self.config['inputs'].remove(input_name)
            self.config.get('mappings', {}).pop(input_name, None)
            if self.config.get('unique_key_input') == input_name:
                self.config['unique_key_input'] = None

            if input_name in self.input_widgets:
                widget_info = self.input_widgets.pop(input_name)
                # Also remove the radio button from the group
                self.key_button_group.removeButton(widget_info['radio'])
                widget_info['layout_widget'].setParent(None)

    def refresh_tables_and_columns(self):
        self.refresh_tables()
        self.refresh_columns()

    def refresh_tables(self):
        settings = QSettings("MyCompany", "NodeFlow")
        host, user, password, database = settings.value("mysql/host", ""), settings.value("mysql/user", ""), settings.value("mysql/password", ""), settings.value("mysql/database", "")
        if not all([host, user, database]):
            QMessageBox.warning(self, "MySQL Not Configured", "Please configure MySQL connection in Application Settings.")
            return
        manager = MySQLManager(host, user, password, database)
        success, msg = manager.connect()
        if not success:
            QMessageBox.critical(self, "Connection Failed", f"Could not connect to database.\n{msg}")
            return
        tables = manager.get_all_tables()
        manager.close()
        if isinstance(tables, list):
            current_table = self.config.get('table_name', '')
            self.table_name_combo.clear()
            self.table_name_combo.addItems(tables)
            if current_table in tables:
                self.table_name_combo.setCurrentText(current_table)
            elif tables:
                self.table_name_combo.setCurrentIndex(0)

    def refresh_columns(self):
        table_name = self.table_name_combo.currentText()
        if not table_name:
            self.available_columns = []
        else:
            settings = QSettings("MyCompany", "NodeFlow")
            host, user, password, database = settings.value("mysql/host", ""), settings.value("mysql/user", ""), settings.value("mysql/password", ""), settings.value("mysql/database", "")
            if not all([host, user, database]):
                self.available_columns = []
            else:
                manager = MySQLManager(host, user, password, database)
                success, msg = manager.connect()
                if not success: self.available_columns = []
                else:
                    columns = manager.get_table_columns(table_name)
                    self.available_columns = [] if isinstance(columns, str) and columns.startswith("Error:") else columns
                    manager.close()
        for widget_info in self.input_widgets.values():
            combo = widget_info['combo']
            current_selection = combo.currentText()
            combo.clear()
            combo.addItems(self.available_columns)
            if current_selection in self.available_columns:
                combo.setCurrentText(current_selection)

    def get_config(self):
        self.config['table_name'] = self.table_name_combo.currentText()
        new_inputs, new_mappings = [], {}
        self.config['unique_key_input'] = None
        for old_name, widget_info in self.input_widgets.items():
            new_name = widget_info['label_widget'].text()
            if new_name:
                new_inputs.append(new_name)
                new_mappings[new_name] = widget_info['combo'].currentText()
                if widget_info['radio'].isChecked():
                    self.config['unique_key_input'] = new_name
        self.config['inputs'] = new_inputs
        self.config['mappings'] = new_mappings
        self.config['label'] = f"Write to {self.config['table_name']}"
        return self.config

class DebugState(Enum):
    """Enumeration for the different states of the sequence debugger."""
    IDLE = 0
    RUNNING = 1
    PAUSED = 2

class NodeType(Enum):
    """Defines the different types of nodes available in the sequencer."""
    METHOD_CALL = "Method Call"
    DELAY = "Delay"
    WRITE_VALUE = "Write Value"
    STATIC_VALUE = "Static Value"
    RUN_SEQUENCE = "Run Sequence"
    COMMENT = "Comment"
    FOR_LOOP = "For Loop"
    WHILE_LOOP = "While Loop"
    COMPUTE = "Compute"
    FORK = "Fork"
    JOIN = "Join"
    SET_VARIABLE = "Set Variable"
    GET_VARIABLE = "Get Variable"
    PYTHON_SCRIPT = "Python Script"
    MYSQL_WRITE = "MySQL Write"
    MYSQL_READ = "MySQL Read"

class CommentNode(QGraphicsTextItem):
    """
    A QGraphicsTextItem for adding editable, movable comments to the scene.

    Args:
        text (str): The initial text of the comment.
        uuid_str (str, optional): The UUID for the node. If None, a new one is generated.
    """
    def __init__(self, text, uuid_str=None):
        super().__init__(text)
        self.uuid = uuid_str or str(uuid.uuid4())
        self.setFlag(QGraphicsObject.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsObject.GraphicsItemFlag.ItemIsSelectable)
        self.setFlag(QGraphicsObject.GraphicsItemFlag.ItemIsFocusable)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
        self.setDefaultTextColor(QColor("#FFFFFF"))
        font = QFont()
        font.setPointSize(12)
        self.setFont(font)

    def serialize(self):
        """
        Serializes the comment node's state to a dictionary.

        Returns:
            dict: A dictionary containing the node's UUID, type, text, and position.
        """
        return {
            'uuid': self.uuid,
            'config': {'node_type': NodeType.COMMENT.value, 'text': self.toPlainText()},
            'pos': {'x': self.pos().x(), 'y': self.pos().y()}
        }

class WhileLoopDialog(QDialog):
    """A dialog for configuring the condition of a While Loop node."""
    def __init__(self, parent=None, current_config=None):
        """
        Initializes the WhileLoopDialog.

        Args:
            parent (QWidget, optional): The parent widget. Defaults to None.
            current_config (dict, optional): The existing configuration to populate the dialog with.
        """
        super().__init__(parent)
        self.setWindowTitle("Configure While Loop Condition")
        self.config = current_config or {}
        layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        self.condition_type_combo = QComboBox()
        self.condition_type_combo.addItems(["is not", "is"])
        self.value_input = QLineEdit()
        self.value_input.setPlaceholderText("Value (e.g., True, 10, 'STOP')")
        form_layout.addRow("Loop while input value:", self.condition_type_combo)
        form_layout.addRow("this value:", self.value_input)
        layout.addLayout(form_layout)
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        negate = self.config.get('while_negate_condition', True)
        self.condition_type_combo.setCurrentText("is not" if negate else "is")
        self.value_input.setText(str(self.config.get('while_condition_value', '')))

    def get_config(self):
        """
        Retrieves the updated configuration from the dialog.

        Returns:
            dict: The updated configuration dictionary for the node.
        """
        self.config['while_negate_condition'] = (self.condition_type_combo.currentText() == "is not")
        self.config['while_condition_value'] = self.value_input.text()
        negate_str = "!" if self.config['while_negate_condition'] else ""
        self.config['label'] = f"While ({negate_str}{self.config['while_condition_value']})"
        return self.config

class RunSequenceDialog(QDialog):
    """A dialog for configuring the RunSequenceNode."""
    def __init__(self, parent=None, current_config=None, available_sequences=None, current_sequence=None):
        """
        Initializes the RunSequenceDialog.

        Args:
            parent (QWidget, optional): The parent widget.
            current_config (dict, optional): The existing node configuration.
            available_sequences (list[str], optional): A list of all sequence names in the project.
            current_sequence (str, optional): The name of the sequence this node belongs to,
                                              to prevent recursive loops.
        """
        super().__init__(parent)
        self.setWindowTitle("Configure Run Sequence Node")
        self.config = current_config or {}

        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        self.sequence_combo = QComboBox()
        if available_sequences:
            filtered_sequences = [name for name in available_sequences if name != current_sequence]
            self.sequence_combo.addItems(filtered_sequences)

        form_layout.addRow("Sequence to Run:", self.sequence_combo)

        layout.addLayout(form_layout)
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        if self.config.get('sequence_name'):
            self.sequence_combo.setCurrentText(self.config['sequence_name'])

    def get_config(self):
        """
        Retrieves the updated configuration from the dialog.

        Returns:
            dict: The updated configuration dictionary, or None if validation fails.
        """
        selected_sequence = self.sequence_combo.currentText()
        if not selected_sequence:
            show_error_message("Configuration Error", "You must select a sequence to run.")
            return None

        self.config['sequence_name'] = selected_sequence
        self.config['label'] = f"Run: {selected_sequence}"
        return self.config

class StaticValueDialog(QDialog):
    """A simple dialog for configuring the StaticValueNode."""
    def __init__(self, parent=None, current_config=None):
        """
        Initializes the StaticValueDialog.

        Args:
            parent (QWidget, optional): The parent widget.
            current_config (dict, optional): The existing node configuration.
        """
        super().__init__(parent)
        self.setWindowTitle("Configure Static Value Node")
        self.config = current_config or {}
        layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        self.value_input = QLineEdit(self.config.get('static_value', ''))
        self.value_input.setPlaceholderText("Enter the value to output (e.g., 123.4 or 'ON')")
        form_layout.addRow("Value:", self.value_input)
        layout.addLayout(form_layout)
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def get_config(self):
        """
        Retrieves the updated configuration from the dialog.

        Returns:
            dict: The updated configuration dictionary.
        """
        self.config['static_value'] = self.value_input.text()
        self.config['label'] = f"Value: {self.config['static_value']}"
        return self.config

class WriteValueDialog(QDialog):
    """A simple dialog for configuring the WriteValueNode."""
    def __init__(self, parent=None, current_config=None):
        """
        Initializes the WriteValueDialog.

        Args:
            parent (QWidget, optional): The parent widget.
            current_config (dict, optional): The existing node configuration.
        """
        super().__init__(parent)
        self.setWindowTitle("Configure Write Value Node")
        self.config = current_config or {}
        layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        self.node_id_input = QLineEdit(self.config.get('node_id', ''))
        self.node_id_input.setPlaceholderText("e.g., ns=2;i=1234")
        self.value_input = QLineEdit(self.config.get('argument_value', ''))
        self.value_input.setPlaceholderText("Value to write (e.g., 123.4 or 'ON')")
        form_layout.addRow("Target Node ID:", self.node_id_input)
        form_layout.addRow("Static Value to Write:", self.value_input)
        layout.addLayout(form_layout)
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def get_config(self):
        """
        Retrieves the updated configuration from the dialog.

        Returns:
            dict: The updated configuration dictionary.
        """
        self.config['node_id'] = self.node_id_input.text()
        self.config['value_to_write'] = self.value_input.text()
        return self.config

class Port(QGraphicsObject):
    """
    A visual port on a SequenceNode for execution flow connections.

    Args:
        parent (QGraphicsItem): The parent node.
        is_output (bool, optional): True if this is an output port, False for input.
        label (str, optional): An optional label for the port (e.g., for loop outputs).
    """
    def __init__(self, parent, is_output=False, label=None):
        super().__init__(parent)
        self.is_output, self.radius = is_output, 6
        self.setFlag(QGraphicsObject.GraphicsItemFlag.ItemSendsScenePositionChanges)
        self.connections = []
        self.label = label
        if self.label:
            self.label_item = QGraphicsTextItem(self.label, self)
            self.label_item.setDefaultTextColor(Qt.GlobalColor.white)
            if self.is_output:
                self.label_item.setPos(self.radius + 5, -self.label_item.boundingRect().height() / 2)
            else:
                self.label_item.setPos(-self.radius - 5 - self.label_item.boundingRect().width(), -self.label_item.boundingRect().height() / 2)

    def boundingRect(self):
        """Returns the bounding rectangle of the port."""
        return QRectF(-self.radius, -self.radius, 2 * self.radius, 2 * self.radius)

    def paint(self, painter, option, widget=None):
        """Paints the port as a circle."""
        painter.setBrush(QBrush(QColor("#5a98d1")))
        painter.setPen(QPen(Qt.GlobalColor.white, 1))
        painter.drawEllipse(-self.radius, -self.radius, 2 * self.radius, 2 * self.radius)

    def itemChange(self, change, value):
        """
        Updates connected connections when the port's position changes.

        Args:
            change (QGraphicsItem.GraphicsItemChange): The type of change.
            value: The new value.

        Returns:
            The result of the parent's itemChange method.
        """
        if change == QGraphicsObject.GraphicsItemChange.ItemScenePositionHasChanged:
            for conn in self.connections: conn.update_path()
        return value

class Connection(QGraphicsPathItem):
    """
    A visual execution connection between two Ports.

    Args:
        start_port (Port): The port where the connection starts.
        end_port (Port): The port where the connection ends.
        scene (QGraphicsScene): The scene containing the connection.
    """
    def __init__(self, start_port, end_port, scene):
        super().__init__()
        self.start_port, self.end_port, self._scene = start_port, end_port, scene
        self.setZValue(-1)
        self.setFlag(QGraphicsPathItem.GraphicsItemFlag.ItemIsSelectable)
        self.condition, self.state = None, "idle"
        self.condition_label = QGraphicsTextItem(self)
        self.condition_label.setDefaultTextColor(QColor("#a9d1ff"))
        self.start_port.connections.append(self)
        if self.end_port: self.end_port.connections.append(self)
        self.update_path()

    def shape(self):
        """
        Returns a wider shape for easier mouse interaction.

        Returns:
            QPainterPath: The stroked shape of the connection.
        """
        stroker = QPainterPathStroker(); stroker.setWidth(10)
        return stroker.createStroke(self.path())

    def set_state(self, new_state):
        """
        Sets the visual state of the connection (e.g., 'active', 'idle').

        Args:
            new_state (str): The new state.
        """
        self.state = new_state; self.update()

    def paint(self, painter, option, widget=None):
        """
        Paints the connection path.

        The color changes based on its execution state (idle/active) or
        if it is selected.

        Args:
            painter (QPainter): The painter to use for drawing.
            option (QStyleOptionGraphicsItem): Provides style options.
            widget (QWidget, optional): The widget being painted on. Defaults to None.
        """
        color = "#f0e68c" if self.state == "active" else "#ffffff"
        width = 3 if self.state == "active" else 2
        pen = QPen(QColor(color), width)
        if self.isSelected(): pen.setColor(QColor("#ffc400"))
        painter.setPen(pen); painter.drawPath(self.path())

    def set_condition(self, condition):
        """
        Sets the condition for this connection and updates the label.

        Args:
            condition (dict): The condition dictionary.
        """
        self.condition = condition
        label_text = ''
        if self.condition:
            if self.condition.get('type') == 'expression':
                expr = self.condition.get('expression', '')
                if len(expr) > 20: expr = expr[:17] + '...'
                label_text = f"fx: {expr}" if expr else ""
            else:
                op = self.condition.get('operator', '')
                if op != "No Condition": label_text = op
        self.condition_label.setPlainText(label_text); self.update_path()

    def update_path(self):
        """Recalculates and sets the cubic bezier path for the connection."""
        path = QPainterPath()
        start_pos = self.start_port.scenePos()
        end_pos = self.end_port.scenePos() if self.end_port else self._scene.mouse_move_pos
        path.moveTo(start_pos)
        offset = 50.0
        ctrl1 = QPointF(start_pos.x() + offset, start_pos.y())
        ctrl2 = QPointF(end_pos.x() - offset, end_pos.y())
        path.cubicTo(ctrl1, ctrl2, end_pos)
        self.setPath(path)
        label_pos = path.pointAtPercent(0.5)
        label_rect = self.condition_label.boundingRect()
        self.condition_label.setPos(label_pos.x() - label_rect.width() / 2, label_pos.y() - label_rect.height() / 2 - 15)

    def destroy(self):
        """Removes the connection from its ports and the scene."""
        if self.start_port and self in self.start_port.connections: self.start_port.connections.remove(self)
        if self.end_port and self in self.end_port.connections: self.end_port.connections.remove(self)
        self._scene.removeItem(self)

    def serialize(self):
        """
        Serializes the connection's state to a dictionary.

        Returns:
            dict or None: A dictionary with connection data, or None if incomplete.
        """
        if not self.start_port or not self.end_port: return None
        return {'start_node_uuid': self.start_port.parentItem().uuid, 'end_node_uuid': self.end_port.parentItem().uuid, 'condition': self.condition}

class SequenceEngine(QObject):
    """
    The backend logic engine that executes a sequence graph.

    This class is decoupled from the UI and handles the step-by-step execution
    of a sequence. It emits signals to notify the UI about state changes,
    pauses, and completion.

    Attributes:
        execution_paused (pyqtSignal): Emitted when the execution pauses at a breakpoint.
                                       Passes sequence_name (str) and node_uuid (str).
        execution_finished (pyqtSignal): Emitted when a sequence completes or is stopped.
                                         Passes sequence_name (str) and was_stopped (bool).
        node_state_changed (pyqtSignal): Emitted when a node's visual state changes.
                                         Passes sequence_name, node_uuid, and state (str).
        connection_state_changed (pyqtSignal): Emitted when a connection's visual state changes.
                                               Passes sequence_name, start_uuid, end_uuid, and state (str).
    """
    execution_paused = pyqtSignal(str, str)
    execution_finished = pyqtSignal(str, bool)
    node_state_changed = pyqtSignal(str, str, str)
    connection_state_changed = pyqtSignal(str, str, str, str)
    global_variable_changed = pyqtSignal(str, object)

    def __init__(self, opcua_logic, async_runner, global_variables):
        """
        Initializes the SequenceEngine.

        Args:
            opcua_logic (OpcuaClientLogic): The OPC-UA logic handler.
            async_runner (AsyncRunner): The utility for running async tasks.
            global_variables (dict): A dictionary for storing global variables.
        """
        super().__init__()
        self.opcua_logic = opcua_logic
        self.async_runner = async_runner
        self.global_variables = global_variables
        self.is_running = False
        self.debug_state = DebugState.IDLE
        self._stop_requested = False
        self.current_sequence_name = ""
        self.is_looping = False
        self.execution_context = {}
        self.data_connection_values = {}
        self.all_sequences = {}
        self._pause_event = asyncio.Event()
        self._step_event = asyncio.Event()
        self._step_into = False

    def resume(self):
        """Resumes execution if it is currently paused."""
        logging.debug(f"RESUME BUTTON CLICKED. Current state: {self.debug_state}")
        if self.debug_state == DebugState.PAUSED:
            self._pause_event.set()

    def step_over(self):
        """Executes the current node and pauses at the next one in the same sequence."""
        logging.debug("STEP OVER BUTTON CLICKED. Current state: {}".format(self.debug_state))
        if self.debug_state == DebugState.PAUSED:
            self._step_into = False
            self._step_event.set()
            self._pause_event.set()

    def step_into(self):
        """Executes the current node, stepping into sub-sequences if applicable."""
        logging.debug("STEP INTO BUTTON CLICKED. Current state: {}".format(self.debug_state))
        if self.debug_state == DebugState.PAUSED:
            self._step_into = True
            self._step_event.set()
            self._pause_event.set()

    def run(self, sequence_name, all_sequences, loop=False):
        """
        Starts the execution of a sequence.

        Args:
            sequence_name (str): The name of the sequence to run.
            all_sequences (dict): A dictionary containing all sequences in the project.
            loop (bool, optional): If True, the sequence will loop indefinitely.
        """
        if self.debug_state != DebugState.IDLE: return

        self.current_sequence_name = sequence_name
        self.is_looping = loop
        self.all_sequences = all_sequences
        self.execution_context.clear()

        main_sequence_data = self.all_sequences.get(sequence_name)
        if not main_sequence_data:
            logging.error(f"Could not find sequence data for '{sequence_name}'.")
            return

        start_node = self.find_start_node(main_sequence_data)
        if not start_node:
            logging.error(f"No start node found for sequence '{sequence_name}'.")
            self.execution_finished.emit(self.current_sequence_name, False)
            return

        self.debug_state = DebugState.RUNNING
        self.is_running = True
        self._stop_requested = False
        self._pause_event.set()
        self.async_runner.submit(self._run_main_loop(start_node, main_sequence_data))

    def stop(self):
        """Requests a graceful stop of the current execution."""
        if self.debug_state != DebugState.IDLE:
            logging.info("Stop requested for sequence execution.")
            self.is_looping = False
            self._stop_requested = True
            self.resume()

    async def _run_main_loop(self, start_node, sequence_data):
        """
        The top-level async loop that handles the 'loop' toggle.

        This method repeatedly calls `_execute_graph` if looping is enabled.

        Args:
            start_node (dict): The node to start execution from.
            sequence_data (dict): The data for the entire sequence.
        """
        try:
            await self._execute_graph(self.current_sequence_name, start_node, sequence_data)
        finally:
            logging.info(f"Execution cycle for '{self.current_sequence_name}' finished.")

            if self.is_looping and not self._stop_requested:
                logging.info(f"Looping sequence '{self.current_sequence_name}'. Restarting...")
                await asyncio.sleep(0.5)
                self.async_runner.submit(self._run_main_loop(start_node, sequence_data))
            else:
                self.debug_state = DebugState.IDLE
                self.is_running = False
                was_stopped = self._stop_requested
                self._stop_requested = False
                self.is_looping = False
                self.execution_finished.emit(self.current_sequence_name, was_stopped)

    async def _execute_graph(self, sequence_name, start_node, sequence_data, is_sub_sequence=False):
        """
        Executes a given sequence graph from a start node.

        This method walks the graph node by node, executing each one and
        following the conditional execution paths. It can be called recursively
        for sub-sequences.

        Args:
            sequence_name (str): The name of the sequence being executed.
            start_node (dict): The node to start execution from.
            sequence_data (dict): The data for the entire sequence.
            is_sub_sequence (bool, optional): True if this is a sub-sequence call.

        Returns:
            tuple: A tuple containing the final result and a success boolean.
        """
        active_connection_data = None
        current_node = start_node

        node_map = {node_data['uuid']: node_data for node_data in sequence_data.get('nodes', [])}

        while current_node and not self._stop_requested:
            if current_node.get('has_breakpoint') and self._pause_event.is_set():
                if not (is_sub_sequence and not self._step_into):
                    self.debug_state = DebugState.PAUSED
                    self._pause_event.clear()
                    self.execution_paused.emit(sequence_name, current_node['uuid'])

            await self._pause_event.wait()

            if self.debug_state == DebugState.PAUSED:
                self.debug_state = DebugState.RUNNING
                await self._step_event.wait()
                self._step_event.clear()

            if active_connection_data:
                self.connection_state_changed.emit(sequence_name, active_connection_data['start_node_uuid'], active_connection_data['end_node_uuid'], "idle")
                await asyncio.sleep(0.1)

            self.node_state_changed.emit(sequence_name, current_node['uuid'], "running")

            value, success = await self.execute_node(current_node, self._step_into)

            if not success:
                if value == "WAITING_FOR_JOIN":
                    logging.debug(f"Branch execution paused, waiting for join at node {current_node['uuid']}.")
                    return None, True
                else:
                    self.node_state_changed.emit(sequence_name, current_node['uuid'], "failed")
                    return None, False

            self.node_state_changed.emit(sequence_name, current_node['uuid'], "success")
            await asyncio.sleep(0.2)

            next_node_uuid, active_connection_data = self.find_next_node_and_connection(current_node, value, sequence_data)

            if active_connection_data:
                self.connection_state_changed.emit(sequence_name, active_connection_data['start_node_uuid'], active_connection_data['end_node_uuid'], "active")
                await asyncio.sleep(0.2)

            current_node = node_map.get(next_node_uuid) if next_node_uuid else None

        if active_connection_data:
            self.connection_state_changed.emit(sequence_name, active_connection_data['start_node_uuid'], active_connection_data['end_node_uuid'], "idle")

        return value, True

    async def execute_node(self, node_data, step_into=False):
        """
        Routes execution to the appropriate method based on node type.

        Args:
            node_data (dict): The data for the node to execute.
            step_into (bool, optional): If true, debugger will step into sub-sequences.

        Returns:
            tuple: A tuple containing the node's result and a success boolean.
        """
        node_type = node_data['config'].get('node_type')
        execution_map = {
            NodeType.METHOD_CALL.value: self.execute_method_call_node,
            NodeType.DELAY.value: self.execute_delay_node,
            NodeType.WRITE_VALUE.value: self.execute_write_value_node,
            NodeType.STATIC_VALUE.value: self.execute_static_value_node,
            NodeType.RUN_SEQUENCE.value: lambda data: self.execute_run_sequence_node(data, step_into),
            NodeType.FOR_LOOP.value: self.execute_for_loop_node,
            NodeType.WHILE_LOOP.value: self.execute_while_loop_node,
            NodeType.COMPUTE.value: self.execute_compute_node,
            NodeType.SET_VARIABLE.value: self.execute_set_variable_node,
            NodeType.GET_VARIABLE.value: self.execute_get_variable_node,
            NodeType.FORK.value: self.execute_fork_node,
            NodeType.JOIN.value: self.execute_join_node,
            NodeType.PYTHON_SCRIPT.value: self.execute_python_script_node,
            NodeType.MYSQL_WRITE.value: self.execute_mysql_write_node,
            NodeType.MYSQL_READ.value: self.execute_mysql_read_node,
        }
        executor = execution_map.get(node_type)
        if executor:
            return await executor(node_data)
        else:
            logging.error(f"Unknown node type '{node_type}' for node '{node_data['config']['label']}'")
            return None, False

    async def execute_compute_node(self, node_data):
        """
        Evaluates a mathematical or logical expression using data inputs.

        Args:
            node_data (dict): The data for the compute node.

        Returns:
            tuple: A tuple containing the expression's result and a success boolean.
        """
        try:
            config = node_data['config']
            expression = config.get('expression')
            if not expression:
                raise ValueError("Compute node has no expression.")

            local_vars = {}
            current_sequence_data = self.all_sequences[self.current_sequence_name]
            data_connections = current_sequence_data.get('data_connections', [])

            for conn in data_connections:
                if conn['end_node_uuid'] == node_data['uuid']:
                    input_label = conn.get('end_socket_label')
                    source_uuid = conn['start_node_uuid']
                    if input_label and source_uuid in self.execution_context:
                        local_vars[input_label] = self.execution_context[source_uuid]
                    else:
                        logging.warning(f"Could not find pre-computed value for input '{input_label}' from node '{source_uuid}'.")
                        return None, False

            logging.info(f"Evaluating expression: '{expression}' with inputs: {local_vars}")
            # Extract the 'value' from each input dictionary if it's a dict, otherwise use the value directly
            eval_vars = {k: v['value'] if isinstance(v, dict) and 'value' in v else v for k, v in local_vars.items()}
            result = eval(expression, {"__builtins__": None}, eval_vars)
            logging.info(f"Expression result: {result}")
            self.execution_context[node_data['uuid']] = result
            return result, True
        except Exception as e:
            logging.error(f"Failed to execute compute node '{node_data['config'].get('label', 'N/A')}': {e}")
            return None, False

    async def execute_while_loop_node(self, node_data):
        """
        Executes a while loop node.

        The loop continues as long as a condition, based on a data input,
        is met. The condition is re-evaluated at the start of each iteration.

        Args:
            node_data (dict): The data for the while loop node.

        Returns:
            tuple: A tuple containing the final result ("Finished") and a success boolean.
        """
        current_sequence_data = self.all_sequences[self.current_sequence_name]
        node_map = {n['uuid']: n for n in current_sequence_data['nodes']}

        negate_condition = node_data['config'].get('while_negate_condition', True)
        condition_target_str = node_data['config'].get('while_condition_value', '')

        loop_body_start_node_uuid, _ = self.find_next_node_and_connection(node_data, "Loop Body", current_sequence_data)
        if not loop_body_start_node_uuid:
            logging.warning("While Loop has no 'Loop Body' connected.")
            return "Finished", True

        loop_start_node = node_map.get(loop_body_start_node_uuid)

        source_node_uuid = next((conn['start_node_uuid'] for conn in current_sequence_data.get('data_connections', []) if conn['end_node_uuid'] == node_data['uuid']), None)
        if not source_node_uuid:
            logging.error("While Loop requires a data input connection for its condition.")
            return None, False

        source_node_data = node_map.get(source_node_uuid)
        if not source_node_data:
            logging.error(f"Could not find the source node ({source_node_uuid}) for the While Loop condition.")
            return None, False

        iteration_count = 0
        max_iterations = 1000
        while iteration_count < max_iterations:
            if self._stop_requested: break

            self.node_state_changed.emit(self.current_sequence_name, source_node_data['uuid'], "running")
            live_value, success = await self.execute_node(source_node_data)
            self.node_state_changed.emit(self.current_sequence_name, source_node_data['uuid'], "success" if success else "failed")

            if not success:
                logging.error("Failed to evaluate While Loop condition.")
                return None, False

            try:
                if isinstance(live_value, bool):
                    condition_target = condition_target_str.lower() in ['true', '1', 't']
                elif isinstance(live_value, (int, float)):
                    condition_target = type(live_value)(condition_target_str)
                else:
                    condition_target = str(condition_target_str)
            except (ValueError, TypeError):
                condition_target = str(condition_target_str)

            is_match = (live_value == condition_target)

            if negate_condition:
                if is_match: break
            else:
                if not is_match: break

            logging.info(f"While Loop condition met. Executing loop body (Iteration {iteration_count + 1}).")
            if loop_start_node:
                await self._execute_graph(self.current_sequence_name, loop_start_node, current_sequence_data, is_sub_sequence=True)

            iteration_count += 1
            await asyncio.sleep(0.01)

        if iteration_count >= max_iterations:
            logging.warning(f"While Loop exceeded maximum iterations ({max_iterations}).")

        return "Finished", True

    async def execute_for_loop_node(self, node_data):
        """
        Executes a for loop node.

        The loop body is executed a fixed number of times as configured in the node.

        Args:
            node_data (dict): The data for the for loop node.

        Returns:
            tuple: A tuple containing the final result ("Finished") and a success boolean.
        """
        iterations = int(node_data['config'].get('iterations', 1))

        loop_body_start_node_uuid, _ = self.find_next_node_and_connection(node_data, "Loop Body", self.all_sequences[self.current_sequence_name])

        if not loop_body_start_node_uuid:
            logging.warning("For Loop has no 'Loop Body' connected.")
        else:
            node_map = {n['uuid']: n for n in self.all_sequences[self.current_sequence_name]['nodes']}
            for i in range(iterations):
                if self._stop_requested:
                    break

                logging.info(f"For Loop iteration {i + 1}/{iterations}")
                loop_start_node = node_map.get(loop_body_start_node_uuid)
                if loop_start_node:
                    await self._execute_graph(self.current_sequence_name, loop_start_node, self.all_sequences[self.current_sequence_name], is_sub_sequence=True)

        return "Finished", True

    async def execute_run_sequence_node(self, node_data, step_into=False):
        """
        Executes another sequence as a sub-routine.

        This allows for modular and reusable sequences.

        Args:
            node_data (dict): The data for the 'Run Sequence' node.
            step_into (bool): Passed to the sub-sequence execution to control debugging.

        Returns:
            tuple: The result and success status from the sub-sequence execution.
        """
        sub_sequence_name = node_data['config'].get('sequence_name')
        if not sub_sequence_name:
            logging.error("Run Sequence node has no sequence name configured.")
            return None, False

        sub_sequence_data = self.all_sequences.get(sub_sequence_name)
        if not sub_sequence_data:
            logging.error(f"Could not find sub-sequence data for '{sub_sequence_name}'.")
            return None, False

        start_node = self.find_start_node(sub_sequence_data)
        if not start_node:
            logging.error(f"No start node found for sub-sequence '{sub_sequence_name}'.")
            return None, False

        logging.info(f"--- Starting sub-sequence: {sub_sequence_name} ---")
        result, success = await self._execute_graph(sub_sequence_name, start_node, sub_sequence_data, is_sub_sequence=True)
        logging.info(f"--- Finished sub-sequence: {sub_sequence_name} (Success: {success}) ---")

        return result, success

    async def resolve_argument_value(self, node_data, sequence_name):
        """
        Determines the value to be used as an argument for a node.

        It can be a static value from the node's configuration or a dynamic
        value from an incoming data connection.

        Args:
            node_data (dict): The data for the node requiring the argument.
            sequence_name (str): The name of the current sequence.

        Returns:
            The resolved argument value.

        Raises:
            ValueError: If the node is configured to use a data connection
                        but one is not found or the source has not executed.
        """
        node_config = node_data['config']
        if not node_config.get("has_argument") or not node_config.get("use_connected_input", False):
            arg_text = node_config.get("argument_value", "")
            try:
                return float(arg_text)
            except (ValueError, TypeError):
                return arg_text

        data_connections = self.all_sequences.get(sequence_name, {}).get('data_connections', [])
        source_node_uuid = None
        connection_uuid = None
        for conn in data_connections:
            if conn['end_node_uuid'] == node_data['uuid']:
                source_node_uuid = conn['start_node_uuid']
                connection_uuid = conn.get('uuid')
                break

        if source_node_uuid:
            if source_node_uuid in self.execution_context:
                value = self.execution_context[source_node_uuid]
                if connection_uuid:
                    self.data_connection_values[connection_uuid] = value
                logging.info(f"Resolved argument for node '{node_config['label']}' from connection. Value: {value}")
                return value
            else:
                raise ValueError(f"Source node '{source_node_uuid}' has not executed or produced a value.")

        raise ValueError(f"Node '{node_config['label']}' is configured to use a connected input, but none is found.")

    async def execute_method_call_node(self, node_data):
        """
        Executes an OPC UA method call node.

        It resolves the argument (if any) from a data connection or static
        value, then calls the specified OPC UA method. The result is stored
        in the execution context.

        Args:
            node_data (dict): The data for the method call node.

        Returns:
            tuple: A tuple containing the method's return value and a success boolean.
        """
        try:
            config = node_data['config']
            parent_id = config['identifier']
            method_bname = config['method_bname']

            parent_node = await self.opcua_logic.find_node(parent_id, "By Node ID")
            if not parent_node: raise Exception(f"Parent node not found: {parent_id}")
            method_node = await self.opcua_logic.get_method_node(parent_node, method_bname)
            if not method_node: raise Exception(f"Method '{method_bname}' not found.")

            args = []
            if config.get("has_argument"):
                current_sequence = self.current_sequence_name
                arg_value = await self.resolve_argument_value(node_data, current_sequence)
                args.append(arg_value)
                logging.info(f"Executing method: {method_bname} with argument: {args[0]}")
            else:
                logging.info(f"Executing method: {method_bname}")

            result = await parent_node.call_method(method_node, *args)
            logging.info(f"Method '{method_bname}' returned: {result}")
            self.execution_context[node_data['uuid']] = result
            return result, True
        except Exception as e:
            logging.error(f"Failed to execute method for node '{node_data['config']['label']}': {e}")
            return None, False

    async def execute_delay_node(self, node_data):
        """
        Executes a delay node.

        Pauses the sequence execution for the configured duration.

        Args:
            node_data (dict): The data for the delay node.

        Returns:
            tuple: A tuple containing True and a success boolean.
        """
        try:
            delay_s = float(node_data['config'].get('delay_seconds', 1.0))
            logging.info(f"Delaying for {delay_s} seconds...")
            await asyncio.sleep(delay_s)
            logging.info("Delay finished.")
            return True, True
        except Exception as e:
            logging.error(f"Failed to execute delay node: {e}")
            return None, False

    async def execute_write_value_node(self, node_data):
        """
        Executes a write value node.

        It resolves the value to write from a data connection or static value,
        then writes it to the specified OPC UA node.

        Args:
            node_data (dict): The data for the write value node.

        Returns:
            tuple: A tuple containing True and a success boolean.
        """
        try:
            config = node_data['config']
            node_id = config.get('node_id')
            if not node_id:
                raise ValueError("Target Node ID must be configured.")

            target_node = await self.opcua_logic.find_node(node_id, "By Node ID")
            if not target_node:
                raise Exception(f"Target node for write not found: {node_id}")

            current_sequence = self.current_sequence_name
            value = await self.resolve_argument_value(node_data, current_sequence)
            datatype = await target_node.read_data_type_as_variant_type()
            logging.info(f"Writing value '{value}' to node {node_id}")
            await self.opcua_logic.write_value(target_node, value, datatype)
            return True, True
        except Exception as e:
            logging.error(f"Failed to execute write value node: {e}")
            return None, False

    async def execute_static_value_node(self, node_data):
        """
        Executes a static value node.

        It outputs a pre-configured, static value which is then placed in the
        execution context to be used by other nodes.

        Args:
            node_data (dict): The data for the static value node.

        Returns:
            tuple: A tuple containing the static value and a success boolean.
        """
        try:
            value_str = node_data['config'].get('static_value', '')
            try:
                value = float(value_str)
            except (ValueError, TypeError):
                value = value_str

            logging.info(f"Node '{node_data['config']['label']}' produced static value: {value}")
            self.execution_context[node_data['uuid']] = value
            return value, True
        except Exception as e:
            logging.error(f"Failed to execute static value node: {e}")
            return None, False

    async def execute_set_variable_node(self, node_data):
        """
        Executes a 'Set Variable' node.

        It resolves an input value and stores it in the shared `global_variables`
        dictionary under a configured name.

        Args:
            node_data (dict): The data for the 'Set Variable' node.

        Returns:
            tuple: A tuple containing True and a success boolean.
        """
        try:
            config = node_data['config']
            variable_name = config.get('variable_name')
            if not variable_name:
                raise ValueError("Variable name is not configured.")

            value_to_set = await self.resolve_argument_value(node_data, self.current_sequence_name)
            self.global_variables[variable_name] = value_to_set
            self.global_variable_changed.emit(variable_name, value_to_set)
            logging.info(f"Set global variable '{variable_name}' to: {value_to_set}")
            return True, True
        except Exception as e:
            logging.error(f"Failed to execute Set Variable node: {e}")
            return None, False

    async def execute_get_variable_node(self, node_data):
        """
        Executes a 'Get Variable' node.

        It retrieves a value from the shared `global_variables` dictionary
        and places it in the execution context for other nodes to use.

        Args:
            node_data (dict): The data for the 'Get Variable' node.

        Returns:
            tuple: A tuple containing the retrieved value and a success boolean.
        """
        try:
            config = node_data['config']
            variable_name = config.get('variable_name')
            if not variable_name:
                raise ValueError("Variable name is not configured.")

            value = self.global_variables.get(variable_name)
            if value is None:
                logging.warning(f"Global variable '{variable_name}' not found. Returning None.")

            self.execution_context[node_data['uuid']] = value
            logging.info(f"Retrieved global variable '{variable_name}'. Value: {value}")
            return value, True
        except Exception as e:
            logging.error(f"Failed to execute Get Variable node: {e}")
            return None, False

    async def execute_fork_node(self, node_data):
        """
        Executes a 'Fork' node.

        It finds all outgoing execution paths and starts a new concurrent task
        for each path using `asyncio.gather`.

        Args:
            node_data (dict): The data for the fork node.

        Returns:
            tuple: A tuple containing True and a success boolean.
        """
        sequence_data = self.all_sequences[self.current_sequence_name]
        node_map = {n['uuid']: n for n in sequence_data['nodes']}

        branches = []
        for conn_data in sequence_data.get('exec_connections', []):
            if conn_data['start_node_uuid'] == node_data['uuid']:
                next_node_uuid = conn_data['end_node_uuid']
                if next_node_uuid in node_map:
                    branches.append(node_map[next_node_uuid])

        if not branches:
            logging.warning(f"Fork node '{node_data['uuid']}' has no outgoing connections.")
            return True, True

        logging.info(f"Forking execution into {len(branches)} branches.")
        tasks = [asyncio.create_task(self._execute_graph(self.current_sequence_name, start_node, sequence_data, is_sub_sequence=True)) for start_node in branches]
        await asyncio.gather(*tasks)
        logging.info(f"All forked branches from '{node_data['uuid']}' have completed.")
        return True, True

    async def execute_python_script_node(self, node_data):
        """
        Executes a 'Python Script' node.

        The script is executed in a restricted scope with access to an 'INPUT'
        variable. The script can set an 'output' variable, which is then
        placed in the execution context.

        Args:
            node_data (dict): The data for the python script node.

        Returns:
            tuple: A tuple containing the script's output and a success boolean.
        """
        try:
            config = node_data['config']
            script = config.get('script', '')
            if not script:
                return None, True

            input_value = await self.resolve_argument_value(node_data, self.current_sequence_name)

            # The script operates on a copy of the global variables, with INPUT and output added.
            script_globals = self.global_variables.copy()
            script_globals['INPUT'] = input_value
            script_globals['output'] = None

            exec(script, script_globals)

            # Changes to global variables made by the script are reflected back.
            for key, value in script_globals.items():
                if key not in ['__builtins__', 'INPUT']:
                    if key not in self.global_variables or self.global_variables[key] != value:
                        self.global_variables[key] = value
                        self.global_variable_changed.emit(key, value)

            output_value = script_globals.get('output')
            self.execution_context[node_data['uuid']] = output_value
            logging.info(f"Python script node executed. Output: {output_value}")
            return output_value, True
        except Exception as e:
            logging.error(f"Failed to execute Python script node: {e}")
            return None, False

    async def execute_mysql_write_node(self, node_data):
        """
        Executes a 'MySQL Write' node.

        It connects to the configured MySQL database, resolves input values,
        and inserts or updates a row in the specified table.
        - If a 'Key' is designated in the node config, it performs an UPSERT.
        - Otherwise, it performs a standard INSERT.
        It will also dynamically add columns to the table if they do not exist.
        """
        try:
            config = node_data['config']
            table_name = config.get('table_name')
            mappings = config.get('mappings', {})
            inputs = config.get('inputs', [])

            if not table_name or not mappings:
                raise ValueError("MySQL Write node is not configured.")

            settings = QSettings("MyCompany", "NodeFlow")
            host, user, password, database = settings.value("mysql/host"), settings.value("mysql/user"), settings.value("mysql/password"), settings.value("mysql/database")
            if not all([host, user, database]):
                raise ConnectionError("MySQL connection details are not configured in settings.")

            manager = MySQLManager(host, user, password, database)
            conn_success, conn_msg = manager.connect()
            if not conn_success:
                raise ConnectionError(f"MySQL connection failed: {conn_msg}")

            try:
                column_values = {}
                for input_name in inputs:
                    column_name = mappings.get(input_name)
                    if not column_name: continue

                    source_node_uuid = next((conn['start_node_uuid'] for conn in self.all_sequences[self.current_sequence_name].get('data_connections', []) if conn['end_node_uuid'] == node_data['uuid'] and conn.get('end_socket_label') == input_name), None)

                    if source_node_uuid and source_node_uuid in self.execution_context:
                        column_values[column_name] = self.execution_context[source_node_uuid]
                    else:
                        logging.warning(f"No input value found for '{input_name}' on MySQL Write node.")
                        column_values[column_name] = None

                if not column_values:
                    logging.warning("MySQL Write node has no values to insert.")
                    return True, True

                db_columns = manager.get_table_columns(table_name)
                if isinstance(db_columns, str) and "1146" in db_columns:
                    manager.execute_query(f"CREATE TABLE `{table_name}` (id INT AUTO_INCREMENT PRIMARY KEY);")
                    db_columns = []

                for col_name in column_values.keys():
                    if col_name not in db_columns:
                        logging.info(f"Column '{col_name}' not found in table '{table_name}'. Adding it.")
                        add_success, add_msg = manager.add_column_to_table(table_name, col_name, "VARCHAR(255)")
                        if not add_success: raise Exception(f"Failed to add column '{col_name}': {add_msg}")

                # UPSERT vs INSERT logic
                unique_key_input = config.get('unique_key_input')
                key_column = mappings.get(unique_key_input) if unique_key_input else None

                columns_str = ', '.join([f"`{c}`" for c in column_values.keys()])
                placeholders = ', '.join(['%s'] * len(column_values))
                values_tuple = tuple(column_values.values())

                if key_column and key_column in column_values:
                    # UPSERT
                    update_pairs = [f"`{col}` = VALUES(`{col}`)" for col in column_values.keys() if col != key_column]
                    if not update_pairs:
                        logging.warning(f"UPSERT for key '{key_column}' has no other columns to update. Performing INSERT instead.")
                        query = f"INSERT IGNORE INTO `{table_name}` ({columns_str}) VALUES ({placeholders})"
                    else:
                        update_clause = ', '.join(update_pairs)
                        query = f"INSERT INTO `{table_name}` ({columns_str}) VALUES ({placeholders}) ON DUPLICATE KEY UPDATE {update_clause}"
                    logging.info(f"Executing MySQL UPSERT: {query} with values {values_tuple}")
                else:
                    # INSERT
                    query = f"INSERT INTO `{table_name}` ({columns_str}) VALUES ({placeholders})"
                    logging.info(f"Executing MySQL INSERT: {query} with values {values_tuple}")

                result = manager.execute_query(query, values_tuple)
                if isinstance(result, str) and result.startswith("Error:"):
                    raise Exception(f"Failed to write to database: {result}")

            finally:
                manager.close()

            return True, True
        except Exception as e:
            logging.error(f"Failed to execute MySQL Write node: {e}")
            return None, False

    async def execute_mysql_read_node(self, node_data):
        """
        Executes a 'MySQL Read' node.

        It connects to the database, executes the configured SELECT query,
        and places the result into the execution context for other nodes to use.
        """
        try:
            config = node_data['config']
            query = config.get('query')

            if not query or not query.strip().upper().startswith("SELECT"):
                raise ValueError("MySQL Read node requires a valid SELECT query.")

            # Load MySQL settings from QSettings
            settings = QSettings("MyCompany", "NodeFlow")
            host = settings.value("mysql/host")
            user = settings.value("mysql/user")
            password = settings.value("mysql/password")
            database = settings.value("mysql/database")

            if not all([host, user, database]):
                raise ConnectionError("MySQL connection details are not configured in settings.")

            manager = MySQLManager(host, user, password, database)
            conn_success, conn_msg = manager.connect()
            if not conn_success:
                raise ConnectionError(f"MySQL connection failed: {conn_msg}")

            try:
                logging.info(f"Executing MySQL Read: {query}")
                result = manager.execute_query(query)
                if isinstance(result, str) and result.startswith("Error:"):
                    raise Exception(f"Failed to execute query: {result}")

                # Store result for the output data socket
                self.execution_context[node_data['uuid']] = result
                logging.info(f"MySQL Read returned {len(result)} rows.")

            finally:
                manager.close()

            return result, True
        except Exception as e:
            logging.error(f"Failed to execute MySQL Read node: {e}")
            return None, False

    async def execute_join_node(self, node_data):
        """
        Executes a 'Join' node.

        This node acts as a synchronization point for forked paths. It counts
        the number of incoming paths and only allows execution to continue
        after all expected paths have arrived.

        Args:
            node_data (dict): The data for the join node.

        Returns:
            tuple: A result and success boolean. If not all paths have arrived,
                   it returns ("WAITING_FOR_JOIN", False) to halt the current path.
        """
        join_uuid = node_data['uuid']

        if join_uuid not in self.execution_context:
            num_incoming = sum(1 for conn in self.all_sequences[self.current_sequence_name].get('exec_connections', []) if conn['end_node_uuid'] == join_uuid)
            self.execution_context[join_uuid] = {'arrivals': 1, 'expected': num_incoming}
            logging.debug(f"Join node '{join_uuid}' first arrival. Expecting {num_incoming} total.")
        else:
            self.execution_context[join_uuid]['arrivals'] += 1
            logging.debug(f"Join node '{join_uuid}' arrival #{self.execution_context[join_uuid]['arrivals']}.")

        context = self.execution_context[join_uuid]
        if context['arrivals'] < context['expected']:
            logging.debug(f"Join node '{join_uuid}' waiting for more arrivals.")
            return "WAITING_FOR_JOIN", False
        else:
            logging.info(f"Join node '{join_uuid}' has received all {context['expected']} arrivals. Continuing execution.")
            del self.execution_context[join_uuid]
            return True, True

    def find_next_node_and_connection(self, current_node_data, result, sequence_data):
        """
        Finds the next node to execute based on outgoing connections and their conditions.

        Args:
            current_node_data (dict): The node that just finished executing.
            result: The output result of the current node.
            sequence_data (dict): The data for the entire sequence.

        Returns:
            tuple: A tuple containing the UUID of the next node and its connection data, or (None, None).
        """
        exec_connections = sequence_data.get('exec_connections', [])
        for conn_data in exec_connections:
            if conn_data['start_node_uuid'] == current_node_data['uuid']:
                if self.evaluate_condition(conn_data, result):
                    return conn_data['end_node_uuid'], conn_data
        return None, None

    def evaluate_condition(self, connection_data, result):
        """
        Evaluates the condition on a connection.

        Args:
            connection_data (dict): The connection's data, including the condition.
            result: The value to test the condition against.

        Returns:
            bool: True if the condition is met or if there is no condition.
        """
        condition = connection_data.get('condition')
        if not condition:
            return True

        if condition.get('type') == 'expression':
            expression = condition.get('expression')
            if not expression: return True
            try:
                return bool(eval(expression, {"__builtins__": {}}, {'INPUT': result}))
            except Exception as e:
                logging.error(f"Error evaluating condition expression '{expression}': {e}")
                return False

        op = condition.get('operator')
        if op == 'No Condition': return True
        if op in ["Loop Body", "Finished"]: return result == op
        if op == "is True": return result is True
        if op == "is False": return result is False
        if 'value' not in condition:
            logging.error(f"Condition '{op}' requires a 'value' but none was found in {condition}.")
            return False

        val_str = condition['value']
        try:
            if isinstance(result, bool):
                val = val_str.lower() in ['true', '1', 't']
            elif isinstance(result, (int, float)):
                val = type(result)(val_str)
            else:
                val = val_str
        except (ValueError, TypeError):
            val = val_str

        ops_map = {"==": lambda a, b: a == b, "!=": lambda a, b: a != b, ">": lambda a, b: a > b,
                   "<": lambda a, b: a < b, ">=": lambda a, b: a >= b, "<=": lambda a, b: a <= b}
        if op in ops_map:
            try:
                return ops_map[op](result, val)
            except TypeError: # Mismatched types
                return False
        return False

    def find_start_node(self, sequence_data):
        """
        Finds the start node of a sequence (a node with no incoming execution connections).

        Args:
            sequence_data (dict): The data for the sequence.

        Returns:
            dict or None: The data for the start node, or None if not found.
        """
        nodes = sequence_data.get('nodes', [])
        if not nodes: return None

        end_node_uuids = {conn['end_node_uuid'] for conn in sequence_data.get('exec_connections', [])}
        for node_data in nodes:
            if node_data['uuid'] not in end_node_uuids:
                return node_data
        return None

class DataSocket(QGraphicsObject):
    """
    A visual socket on a SequenceNode for data flow connections.

    These are represented as small squares and can have labels to distinguish
    them (e.g., for multi-input nodes).
    """
    def __init__(self, parent, is_output=False, label=None):
        """
        Initializes the DataSocket.

        Args:
            parent (QGraphicsItem): The parent node.
            is_output (bool, optional): True if this is an output socket. Defaults to False.
            label (str, optional): An identifying label for the socket. Defaults to None.
        """
        super().__init__(parent)
        self.is_output = is_output
        self.label = label
        self.radius = 5
        self.setFlag(QGraphicsObject.GraphicsItemFlag.ItemSendsScenePositionChanges)
        self.connections = []
        self.setZValue(1)

        if self.label:
            self.label_item = QGraphicsTextItem(self.label, self)
            self.label_item.setDefaultTextColor(QColor("#ffc400"))
            font = self.label_item.font()
            font.setBold(True)
            self.label_item.setFont(font)
            if self.is_output:
                # Label below the socket
                self.label_item.setPos(-self.label_item.boundingRect().width() / 2, self.radius)
            else:
                # Label above the socket
                self.label_item.setPos(-self.label_item.boundingRect().width() / 2, -self.radius - self.label_item.boundingRect().height())

    def boundingRect(self):
        """Returns the bounding rectangle of the socket."""
        return QRectF(-self.radius - 2, -self.radius - 2, 2 * self.radius + 4, 2 * self.radius + 4)

    def paint(self, painter, option, widget=None):
        """
        Paints the socket as a square.

        Args:
            painter (QPainter): The painter to use for drawing.
            option (QStyleOptionGraphicsItem): Provides style options.
            widget (QWidget, optional): The widget being painted on. Defaults to None.
        """
        painter.setBrush(QBrush(QColor("#ffc400")))
        painter.setPen(QPen(Qt.GlobalColor.black, 1))
        painter.drawRect(-self.radius, -self.radius, 2 * self.radius, 2 * self.radius)

    def itemChange(self, change, value):
        """
        Updates connected data connections when the socket's position changes.

        Args:
            change (QGraphicsItem.GraphicsItemChange): The type of change.
            value: The new value.

        Returns:
            The result of the parent's itemChange method.
        """
        if change == QGraphicsObject.GraphicsItemChange.ItemScenePositionHasChanged:
            for conn in self.connections:
                conn.update_path()
        return value

class DataConnection(QGraphicsPathItem):
    """
    A visual data connection between two DataSockets.

    The path is drawn as a smooth Bezier curve.
    """
    def __init__(self, start_socket, end_socket, scene, uuid_str=None):
        """
        Initializes the DataConnection.

        Args:
            start_socket (DataSocket): The socket where the connection starts.
            end_socket (DataSocket): The socket where the connection ends.
            scene (QGraphicsScene): The scene containing the connection.
            uuid_str (str, optional): The UUID for the connection. If None, a new one is generated.
        """
        super().__init__()
        self.uuid = uuid_str or str(uuid.uuid4())
        self.start_socket = start_socket
        self.end_socket = end_socket
        self._scene = scene
        self.setZValue(-1)
        self.setFlag(QGraphicsPathItem.GraphicsItemFlag.ItemIsSelectable)
        self.state = "idle"

        self.start_socket.connections.append(self)
        if self.end_socket:
            self.end_socket.connections.append(self)

        self.update_path()

    def shape(self):
        """
        Returns a wider shape for easier mouse interaction.

        Returns:
            QPainterPath: The stroked shape of the connection.
        """
        stroker = QPainterPathStroker()
        stroker.setWidth(10)
        return stroker.createStroke(self.path())

    def set_state(self, new_state):
        """
        Sets the visual state of the connection (e.g., 'active').

        Args:
            new_state (str): The new state string.
        """
        self.state = new_state
        self.update()

    def paint(self, painter, option, widget=None):
        """
        Paints the connection path.

        Args:
            painter (QPainter): The painter to use for drawing.
            option (QStyleOptionGraphicsItem): Provides style options.
            widget (QWidget, optional): The widget being painted on. Defaults to None.
        """
        color = "#f0e68c" if self.state == "active" else "#ffc400"
        pen = QPen(QColor(color), 2, Qt.PenStyle.DashLine)
        if self.isSelected():
            pen.setColor(QColor("#ffffff"))
            pen.setStyle(Qt.PenStyle.SolidLine)
        painter.setPen(pen)
        painter.drawPath(self.path())

    def update_path(self):
        """Recalculates and sets the smooth Bezier path for the connection."""
        path = QPainterPath()
        start_pos = self.start_socket.scenePos()
        end_pos = self.end_socket.scenePos() if self.end_socket else self._scene.mouse_move_pos
        path.moveTo(start_pos)
        
        # Control points for the Bezier curve
        offset_y = 60.0
        ctrl1 = QPointF(start_pos.x(), start_pos.y() + offset_y)
        ctrl2 = QPointF(end_pos.x(), end_pos.y() - offset_y)
        path.cubicTo(ctrl1, ctrl2, end_pos)
        
        self.setPath(path)

    def destroy(self):
        """Removes the connection from its sockets and the scene."""
        if self.start_socket and self in self.start_socket.connections:
            self.start_socket.connections.remove(self)
        if self.end_socket and self in self.end_socket.connections:
            self.end_socket.connections.remove(self)
        self._scene.removeItem(self)

    def serialize(self):
        """
        Serializes the connection's state to a dictionary.

        Returns:
            dict or None: A dictionary with connection data, or None if incomplete.
        """
        if not self.start_socket or not self.end_socket:
            return None
        return {
            'uuid': self.uuid,
            'start_node_uuid': self.start_socket.parentItem().uuid,
            'end_node_uuid': self.end_socket.parentItem().uuid,
            'end_socket_label': self.end_socket.label if hasattr(self.end_socket, 'label') else None
        }


class SequenceNode(QGraphicsObject):
    """
    The visual representation of a single operation in the sequence.

    This class handles the drawing, configuration, and interaction of a node
    in the editor. It contains ports for execution flow and sockets for data flow.
    The appearance of the node can change based on its type and execution state.
    """
    def __init__(self, config, uuid_str=None):
        """
        Initializes the SequenceNode.

        Args:
            config (dict): The configuration dictionary that defines the node's
                           type, label, and other properties.
            uuid_str (str, optional): The UUID for the node. If None, a new one is generated.
        """
        super().__init__()
        self.config = config
        self.uuid = uuid_str or str(uuid.uuid4())
        self.has_breakpoint = config.get('has_breakpoint', False)

        self.setFlags(QGraphicsObject.GraphicsItemFlag.ItemIsMovable | QGraphicsObject.GraphicsItemFlag.ItemIsSelectable | QGraphicsObject.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.width, self.height = 180, 80
        self.state = "idle"

        self.title = QGraphicsTextItem(self)
        self.title.setDefaultTextColor(Qt.GlobalColor.white)

        font = QFont()
        font.setPointSize(10)
        font.setBold(True)
        self.title.setFont(font)

        self.update_title()

        self.in_port = Port(self, is_output=False)
        self.out_port = Port(self, is_output=True)
        self.in_port.setPos(0, self.height / 2)
        self.out_port.setPos(self.width, self.height / 2)

        self.data_in_socket = None
        self.data_out_socket = None
        self.data_in_sockets = {} # MODIFIED: For multi-input nodes like Compute

        node_type = self.config.get('node_type')

        if node_type == NodeType.METHOD_CALL.value:
            self.data_in_socket = DataSocket(self, is_output=False, label="In")
            self.data_in_socket.setPos(self.width / 2, 0)
            self.data_out_socket = DataSocket(self, is_output=True, label="Out")
            self.data_out_socket.setPos(self.width / 2, self.height)
        elif node_type == NodeType.WRITE_VALUE.value:
            self.data_in_socket = DataSocket(self, is_output=False, label="In")
            self.data_in_socket.setPos(self.width / 2, 0)
        elif node_type == NodeType.STATIC_VALUE.value:
            self.data_out_socket = DataSocket(self, is_output=True, label="Out")
            self.data_out_socket.setPos(self.width / 2, self.height)
        elif node_type == NodeType.COMPUTE.value:
            self.data_in_sockets['A'] = DataSocket(self, is_output=False, label='A'); self.data_in_sockets['A'].setPos(self.width*0.25, 0)
            self.data_in_sockets['B'] = DataSocket(self, is_output=False, label='B'); self.data_in_sockets['B'].setPos(self.width*0.50, 0)
            self.data_in_sockets['C'] = DataSocket(self, is_output=False, label='C'); self.data_in_sockets['C'].setPos(self.width*0.75, 0)
            self.data_out_socket = DataSocket(self, is_output=True, label="Out"); self.data_out_socket.setPos(self.width/2, self.height)
        elif node_type == NodeType.FORK.value:
            self.out_port.hide()
            # We need to store the ports in a way that can be accessed later
            self.out_ports = {}
            labels = ["1", "2", "3"]
            for i, label in enumerate(labels):
                port = Port(self, is_output=True, label=label)
                port.setPos(self.width, self.height * (i + 1) / (len(labels) + 1))
                self.out_ports[label] = port
        elif node_type == NodeType.JOIN.value:
            self.in_port.hide()
            # We need to store the ports in a way that can be accessed later
            self.in_ports = {}
            labels = ["1", "2", "3"]
            for i, label in enumerate(labels):
                port = Port(self, is_output=False, label=label)
                port.setPos(0, self.height * (i + 1) / (len(labels) + 1))
                self.in_ports[label] = port
        elif node_type == NodeType.SET_VARIABLE.value:
            self.data_in_socket = DataSocket(self, is_output=False, label="Value")
            self.data_in_socket.setPos(self.width / 2, 0)
        elif node_type == NodeType.GET_VARIABLE.value:
            self.data_out_socket = DataSocket(self, is_output=True, label="Value")
            self.data_out_socket.setPos(self.width / 2, self.height)
        elif node_type in [NodeType.FOR_LOOP.value, NodeType.WHILE_LOOP.value]:
             self.out_port.hide()
        elif node_type == NodeType.MYSQL_WRITE.value:
            inputs = self.config.get('inputs', [])
            num_inputs = len(inputs)
            for i, input_name in enumerate(inputs):
                socket = DataSocket(self, is_output=False, label=input_name)
                # Distribute sockets along the top edge
                socket.setPos(self.width * (i + 1) / (num_inputs + 1), 0)
                self.data_in_sockets[input_name] = socket
        elif node_type == NodeType.MYSQL_READ.value:
            self.data_out_socket = DataSocket(self, is_output=True, label="Out")
            self.data_out_socket.setPos(self.width / 2, self.height)
        elif node_type == NodeType.PYTHON_SCRIPT.value:
            self.data_in_socket = DataSocket(self, is_output=False, label="In")
            self.data_in_socket.setPos(self.width / 2, 0)
            self.data_out_socket = DataSocket(self, is_output=True, label="Out")
            self.data_out_socket.setPos(self.width / 2, self.height)

    def toggle_breakpoint(self):
        """Toggles the breakpoint state for this node and triggers a repaint."""
        self.has_breakpoint = not self.has_breakpoint
        self.config['has_breakpoint'] = self.has_breakpoint
        self.update() # Trigger a repaint

    def set_state(self, new_state):
        """
        Sets the visual state of the node and triggers a repaint.

        Used for showing execution status (e.g., 'running', 'success').

        Args:
            new_state (str): The new state string.
        """
        self.state = new_state
        self.update()

    def boundingRect(self):
        """Returns the bounding rectangle of the node."""
        return QRectF(0, 0, self.width, self.height)

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget | None = ...):
        """
        Paints the node's shape, color, and breakpoint indicator.

        The color is determined by the node's type, selection state, and execution state.

        Args:
            painter (QPainter): The painter to use for drawing.
            option (QStyleOptionGraphicsItem): Provides style options.
            widget (QWidget, optional): The widget being painted on. Defaults to None.
        """
        path = QPainterPath()
        path.addRoundedRect(self.boundingRect(), 10, 10)

        node_type = self.config.get('node_type')

        # --- Custom Color Logic ---
        if 'custom_color' in self.config:
            base_color = self.config['custom_color']
        else:
            # Default color scheme
            base_color = "#3c3f41"
            if node_type == NodeType.METHOD_CALL.value: base_color = "#2E4053"
            elif node_type == NodeType.DELAY.value: base_color = "#483D8B"
            elif node_type == NodeType.WRITE_VALUE.value: base_color = "#556B2F"
            elif node_type == NodeType.STATIC_VALUE.value: base_color = "#006464"
            elif node_type == NodeType.RUN_SEQUENCE.value: base_color = "#6A1B9A"
            elif node_type == NodeType.FOR_LOOP.value: base_color = "#8B4513"
            elif node_type == NodeType.WHILE_LOOP.value: base_color = "#1E8449"
            elif node_type == NodeType.COMPUTE.value: base_color = "#BF360C"

        state_colors = {"running": "#f0e68c", "success": "#90ee90", "failed": "#ff6347", "paused": "#6495ED"}
        color = state_colors.get(self.state, base_color if not self.isSelected() else "#5a98d1")

        painter.setBrush(QBrush(QColor(color)))
        painter.setPen(QPen(QColor("#888"), 1))
        painter.drawPath(path)

        if self.has_breakpoint:
            painter.setBrush(QBrush(QColor("#e53935"))) # Red color for breakpoint
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(self.width - 20, 5, 15, 15)

    def itemChange(self, change, value):
        """
        Propagates position changes to all connections.

        Args:
            change (QGraphicsItem.GraphicsItemChange): The type of change.
            value: The new value.

        Returns:
            The result of the parent's itemChange method.
        """
        if change == QGraphicsObject.GraphicsItemChange.ItemPositionHasChanged:
            self.in_port.itemChange(QGraphicsObject.GraphicsItemChange.ItemScenePositionHasChanged, None)
            self.out_port.itemChange(QGraphicsObject.GraphicsItemChange.ItemScenePositionHasChanged, None)
            if self.data_in_socket:
                self.data_in_socket.itemChange(QGraphicsObject.GraphicsItemChange.ItemScenePositionHasChanged, None)
            if self.data_out_socket:
                self.data_out_socket.itemChange(QGraphicsObject.GraphicsItemChange.ItemScenePositionHasChanged, None)
            for socket in self.data_in_sockets.values(): # NEW
                socket.itemChange(QGraphicsObject.GraphicsItemChange.ItemScenePositionHasChanged, None)
            if hasattr(self, 'out_port_loop_body'):
                self.out_port_loop_body.itemChange(QGraphicsObject.GraphicsItemChange.ItemScenePositionHasChanged, None)
                self.out_port_finished.itemChange(QGraphicsObject.GraphicsItemChange.ItemScenePositionHasChanged, None)
            if hasattr(self, 'in_ports'):
                for port in self.in_ports.values():
                    port.itemChange(QGraphicsObject.GraphicsItemChange.ItemScenePositionHasChanged, None)
            if hasattr(self, 'out_ports'):
                for port in self.out_ports.values():
                    port.itemChange(QGraphicsObject.GraphicsItemChange.ItemScenePositionHasChanged, None)
        return super().itemChange(change, value)

    def destroy(self):
        """Removes the node and all its connections from the scene."""
        for conn in self.in_port.connections[:]: conn.destroy()
        for conn in self.out_port.connections[:]: conn.destroy()
        if self.data_in_socket:
            for conn in self.data_in_socket.connections[:]: conn.destroy()
        if self.data_out_socket:
            for conn in self.data_out_socket.connections[:]: conn.destroy()
        for socket in self.data_in_sockets.values(): # NEW
            for conn in socket.connections[:]: conn.destroy()
        if hasattr(self, 'out_port_loop_body'):
            for conn in self.out_port_loop_body.connections[:]: conn.destroy()
            for conn in self.out_port_finished.connections[:]: conn.destroy()
        if hasattr(self, 'in_ports'):
            for port in self.in_ports.values():
                for conn in port.connections[:]: conn.destroy()
        if hasattr(self, 'out_ports'):
            for port in self.out_ports.values():
                for conn in port.connections[:]: conn.destroy()
        self.scene().removeItem(self)

    def center_title(self):
        """Calculates and sets the position of the title to be centered in the node."""
        node_rect = self.boundingRect()
        title_rect = self.title.boundingRect()
        x = node_rect.center().x() - title_rect.width() / 2
        y = node_rect.center().y() - title_rect.height() / 2
        self.title.setPos(x, y)

    def update_title(self):
        """Updates the node's title text from its configuration."""
        title_text = self.config.get('label', 'Unknown')
        if self.config.get('has_argument'):
            title_text += " *"
        self.title.setPlainText(title_text)
        self.center_title()

    def update_sockets(self):
        """
        Clears and recreates data sockets based on the node's current configuration.
        This is essential for nodes where the number of inputs/outputs can be
        changed dynamically.
        """
        # Clear existing input data sockets and their connections
        for socket in self.data_in_sockets.values():
            for conn in socket.connections[:]:
                conn.destroy()
            if self.scene():
                self.scene().removeItem(socket)
        self.data_in_sockets.clear()

        node_type = self.config.get('node_type')

        # Re-create sockets for specific node types that support dynamic configuration
        if node_type == NodeType.MYSQL_WRITE.value:
            inputs = self.config.get('inputs', [])
            num_inputs = len(inputs)
            for i, input_name in enumerate(inputs):
                socket = DataSocket(self, is_output=False, label=input_name)
                # Distribute sockets along the top edge
                socket.setPos(self.width * (i + 1) / (num_inputs + 1), 0)
                self.data_in_sockets[input_name] = socket
        elif node_type == NodeType.COMPUTE.value:
            # Re-create the standard 'A', 'B', 'C' sockets
            self.data_in_sockets['A'] = DataSocket(self, is_output=False, label='A')
            self.data_in_sockets['A'].setPos(self.width * 0.25, 0)
            self.data_in_sockets['B'] = DataSocket(self, is_output=False, label='B')
            self.data_in_sockets['B'].setPos(self.width * 0.50, 0)
            self.data_in_sockets['C'] = DataSocket(self, is_output=False, label='C')
            self.data_in_sockets['C'].setPos(self.width * 0.75, 0)

    def serialize(self):
        """
        Serializes the node's state to a dictionary.

        Returns:
            dict: A dictionary containing the node's data.
        """
        return {
            'uuid': self.uuid,
            'config': self.config,
            'pos': {'x': self.pos().x(), 'y': self.pos().y()},
            'has_breakpoint': self.has_breakpoint
        }

    def mousePressEvent(self, event):
        """
        Handles mouse press events on the node.

        Temporarily disables the view's rubber band drag mode to ensure node
        dragging takes precedence.

        Args:
            event (QGraphicsSceneMouseEvent): The mouse press event.
        """
        if self.scene() and self.scene().views():
            self.scene().views()[0].setDragMode(QGraphicsView.DragMode.NoDrag)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        """
        Handles mouse release events on the node.

        Restores the view's rubber band drag mode.

        Args:
            event (QGraphicsSceneMouseEvent): The mouse release event.
        """
        if self.scene() and self.scene().views():
            self.scene().views()[0].setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        super().mouseReleaseEvent(event)

    def highlight(self):
        """Animates the node with a blinking effect to draw attention to it."""
        self.setZValue(10) # Bring to front

        anim = QPropertyAnimation(self, b"opacity")
        anim.setDuration(200)
        anim.setLoopCount(4) # Blink twice
        anim.setKeyValueAt(0.0, 1.0)
        anim.setKeyValueAt(0.5, 0.3)
        anim.setKeyValueAt(1.0, 1.0)
        anim.finished.connect(lambda: self.setZValue(0))
        anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
        self.animation = anim # Keep a reference


class GroupNode(QGraphicsObject):
    """
    A visual container for grouping other nodes together.

    It can be moved (which moves all contained nodes) and resized. Its title
    can be edited by double-clicking.
    """
    def __init__(self, title="Group", uuid_str=None):
        """
        Initializes the GroupNode.

        Args:
            title (str, optional): The initial title of the group. Defaults to "Group".
            uuid_str (str, optional): The UUID for the node. If None, a new one is generated.
        """
        super().__init__()
        self.uuid = uuid_str or str(uuid.uuid4())
        self.setFlag(QGraphicsObject.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsObject.GraphicsItemFlag.ItemIsSelectable)
        self.setZValue(-10)

        self.width = 300
        self.height = 200
        self.title_item = EditableTitleTextItem(title, self)
        self.title_item.setPos(5, 5)

        self.contained_nodes = []

    def boundingRect(self):
        """Returns the bounding rectangle of the group node."""
        return QRectF(0, 0, self.width, self.height)

    def paint(self, painter, option, widget=None):
        """
        Paints the group node as a semi-transparent rounded rectangle.

        Also draws a resize handle in the bottom-right corner.

        Args:
            painter (QPainter): The painter to use for drawing.
            option (QStyleOptionGraphicsItem): Provides style options.
            widget (QWidget, optional): The widget being painted on. Defaults to None.
        """
        path = QPainterPath()
        path.addRoundedRect(self.boundingRect(), 10, 10)

        painter.setBrush(QColor(255, 255, 255, 20))
        painter.setPen(QPen(QColor(200, 200, 200, 100), 2))
        painter.drawPath(path)

        # Draw resize handle
        handle_size = 10
        handle_rect = QRectF(self.width - handle_size, self.height - handle_size, handle_size, handle_size)
        painter.setBrush(QColor(255, 255, 255, 100))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(handle_rect)

    def mouseDoubleClickEvent(self, event):
        """
        Handles double-click events to enable title editing.

        Args:
            event (QGraphicsSceneMouseEvent): The mouse event.
        """
        if self.title_item.boundingRect().contains(event.pos()):
            self.title_item.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
            self.title_item.setFocus()
        super().mouseDoubleClickEvent(event)

    def mousePressEvent(self, event):
        """
        Handles mouse press events to initiate resizing.

        Args:
            event (QGraphicsSceneMouseEvent): The mouse event.
        """
        self.is_resizing = False
        handle_size = 10
        handle_rect = QRectF(self.width - handle_size, self.height - handle_size, handle_size, handle_size)
        if handle_rect.contains(event.pos()):
            self.is_resizing = True
            self.resize_start_pos = event.pos()
            self.resize_start_size = (self.width, self.height)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """
        Handles mouse move events to perform resizing.

        Args:
            event (QGraphicsSceneMouseEvent): The mouse event.
        """
        if self.is_resizing:
            delta = event.pos() - self.resize_start_pos
            self.prepareGeometryChange()
            self.width = self.resize_start_size[0] + delta.x()
            self.height = self.resize_start_size[1] + delta.y()
            self.update()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """
        Handles mouse release events to finalize resizing.

        Args:
            event (QGraphicsSceneMouseEvent): The mouse event.
        """
        self.is_resizing = False
        super().mouseReleaseEvent(event)

    def itemChange(self, change, value):
        """
        Handles changes to the item's state.

        Currently unused for position changes as node movement is handled by parenting.

        Args:
            change (QGraphicsItem.GraphicsItemChange): The type of change.
            value: The new value.

        Returns:
            The result of the parent's itemChange method.
        """
        if change == QGraphicsObject.GraphicsItemChange.ItemPositionHasChanged:
            # This logic will be handled by parenting the nodes to the group
            pass
        return super().itemChange(change, value)

    def add_node(self, node):
        """
        Adds a node to this group.

        The node is added to the internal list and is graphically parented to the group.

        Args:
            node (SequenceNode): The node to add.
        """
        if node not in self.contained_nodes:
            self.contained_nodes.append(node)
            node.setParentItem(self)

    def remove_node(self, node):
        """
        Removes a node from this group.

        The node is removed from the internal list and its parent is reset.

        Args:
            node (SequenceNode): The node to remove.
        """
        if node in self.contained_nodes:
            self.contained_nodes.remove(node)
            node.setParentItem(None)

    def serialize(self):
        """
        Serializes the group node's state to a dictionary.

        Returns:
            dict: A dictionary containing the group's data.
        """
        return {
            'uuid': self.uuid,
            'title': self.title_item.toPlainText(),
            'pos': {'x': self.pos().x(), 'y': self.pos().y()},
            'size': {'width': self.width, 'height': self.height},
            'contained_nodes': [node.uuid for node in self.contained_nodes]
        }


class EditableTitleTextItem(QGraphicsTextItem):
    """
    A QGraphicsTextItem that becomes editable on double-click.

    Used for the title of a GroupNode.
    """
    def __init__(self, text, parent):
        """
        Initializes the EditableTitleTextItem.

        Args:
            text (str): The initial text to display.
            parent (QGraphicsItem): The parent graphics item.
        """
        super().__init__(text, parent)
        self.parent = parent
        self.setPlainText(text)
        self.setDefaultTextColor(Qt.GlobalColor.white)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)

    def focusOutEvent(self, event):
        """
        Disables text editing when the item loses focus.

        Args:
            event (QFocusEvent): The focus event.
        """
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        super().focusOutEvent(event)


class AddNodeCommand(QUndoCommand):
    def __init__(self, scene, config, position, parent=None):
        super().__init__(parent)
        self.scene, self.config, self.position, self.node = scene, config, position, None
        self.setText("Add Node")

    def redo(self):
        if not self.node:
            node_type = self.config.get('node_type')
            if node_type == NodeType.COMMENT.value: self.node = CommentNode(self.config.get('text', 'Comment'))
            else: self.node = SequenceNode(self.config)
            self.node.setPos(self.position)
        self.scene.addItem(self.node); self.scene.clearSelection(); self.node.setSelected(True)
        self.scene.scene_changed.emit()

    def undo(self):
        self.scene.removeItem(self.node); self.scene.clearSelection(); self.scene.scene_changed.emit()

class DeleteItemsCommand(QUndoCommand):
    """Command for deleting one or more items (nodes and connections)."""
    def __init__(self, scene, items_to_delete, parent=None):
        super().__init__(parent)
        self.scene = scene
        self.items_data = []

        # Create a comprehensive set of all items to be deleted, including connections of deleted nodes.
        full_item_set = set(items_to_delete)
        for item in items_to_delete:
            if isinstance(item, SequenceNode):
                # Add all connections from all ports and sockets to the set
                connections_to_add = []
                connections_to_add.extend(item.in_port.connections)
                connections_to_add.extend(item.out_port.connections)

                if item.data_in_socket:
                    connections_to_add.extend(item.data_in_socket.connections)
                if item.data_out_socket:
                    connections_to_add.extend(item.data_out_socket.connections)

                if hasattr(item, 'data_in_sockets'):
                    for socket in item.data_in_sockets.values():
                        connections_to_add.extend(socket.connections)

                if hasattr(item, 'out_port_loop_body'):
                     connections_to_add.extend(item.out_port_loop_body.connections)
                if hasattr(item, 'out_port_finished'):
                     connections_to_add.extend(item.out_port_finished.connections)

                for conn in connections_to_add:
                    full_item_set.add(conn)

        # Now, serialize the full set of items
        for item in full_item_set:
            data = {'item': item}
            if isinstance(item, SequenceNode):
                data['type'] = 'node'
                data['config'] = item.config
                data['pos'] = item.pos()
                data['uuid'] = item.uuid
            elif isinstance(item, CommentNode):
                data['type'] = 'comment'
                data['text'] = item.toPlainText()
                data['pos'] = item.pos()
                data['uuid'] = item.uuid
            elif isinstance(item, Connection):
                data['type'] = 'connection'
                data['start_uuid'] = item.start_port.parentItem().uuid
                data['end_uuid'] = item.end_port.parentItem().uuid if item.end_port else None
                data['condition'] = item.condition
            elif isinstance(item, DataConnection):
                data['type'] = 'data_connection'
                data['start_uuid'] = item.start_socket.parentItem().uuid
                data['end_uuid'] = item.end_socket.parentItem().uuid if item.end_socket else None
                # Save the end socket label for multi-input nodes
                if item.end_socket:
                    data['end_socket_label'] = item.end_socket.label if hasattr(item.end_socket, 'label') else None
                else:
                    data['end_socket_label'] = None

            # Only add items that could be serialized
            if 'type' in data:
                self.items_data.append(data)

        self.setText("Delete Items")

    def redo(self):
        for data in self.items_data:
            # Check if item is still in the scene before removing
            if data['item'].scene() is self.scene:
                self.scene.removeItem(data['item'])
        self.scene.clearSelection()
        self.scene.scene_changed.emit()

    def undo(self):
        nodes_map = {}
        for item in self.scene.items():
            if isinstance(item, (SequenceNode, CommentNode)):
                nodes_map[item.uuid] = item

        # Re-add nodes and comments first
        for data in self.items_data:
            if data['type'] == 'node':
                node = SequenceNode(data['config'], data['uuid'])
                node.setPos(data['pos'])
                self.scene.addItem(node)
                data['item'] = node
                nodes_map[node.uuid] = node
            elif data['type'] == 'comment':
                node = CommentNode(data['text'], data['uuid'])
                node.setPos(data['pos'])
                self.scene.addItem(node)
                data['item'] = node
                nodes_map[node.uuid] = node

        # Then, re-add connections
        for data in self.items_data:
            if data['type'] == 'connection':
                start_node = nodes_map.get(data['start_uuid'])
                end_node = nodes_map.get(data['end_uuid'])
                if start_node and end_node:
                    conn = Connection(start_node.out_port, end_node.in_port, self.scene)
                    if data['condition']:
                        conn.set_condition(data['condition'])
                    self.scene.addItem(conn)
                    data['item'] = conn
            elif data['type'] == 'data_connection':
                start_node = nodes_map.get(data['start_uuid'])
                end_node = nodes_map.get(data['end_uuid'])
                if start_node and end_node:
                    end_socket = None
                    # Find the correct socket on the target node using the saved label
                    socket_label = data.get('end_socket_label')
                    if socket_label and hasattr(end_node, 'data_in_sockets') and end_node.data_in_sockets:
                        end_socket = end_node.data_in_sockets.get(socket_label)
                    elif hasattr(end_node, 'data_in_socket'):
                        end_socket = end_node.data_in_socket

                    if start_node.data_out_socket and end_socket:
                        conn = DataConnection(start_node.data_out_socket, end_socket, self.scene, data.get('uuid'))
                        conn.update_path()
                        self.scene.addItem(conn)
                        data['item'] = conn
        self.scene.scene_changed.emit()


class MoveNodesCommand(QUndoCommand):
    """Command for moving one or more nodes."""
    def __init__(self, nodes, old_positions, new_positions, parent=None):
        super().__init__(parent)
        self.nodes = nodes
        self.old_positions = old_positions
        self.new_positions = new_positions
        self.setText("Move Nodes")

    def redo(self):
        for node, pos in zip(self.nodes, self.new_positions):
            node.setPos(pos)
        self.nodes[0].scene().scene_changed.emit()

    def undo(self):
        for node, pos in zip(self.nodes, self.old_positions):
            node.setPos(pos)
        self.nodes[0].scene().scene_changed.emit()

class SequenceScene(QGraphicsScene):
    """The canvas for the sequencer editor, with a grid background and snap-to-grid functionality."""
    add_new_node_requested = pyqtSignal(NodeType, QPointF)
    scene_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.grid_size = 20
        self.grid_color = QColor(200, 200, 200)
        self.background_color = QColor(40, 42, 45)

        # Set a large scene rectangle for a scrollable/pannable canvas
        self.setSceneRect(-5000, -5000, 10000, 10000)
        self.setBackgroundBrush(self.background_color)

        self.temp_connection = None
        self.mouse_move_pos = QPointF(0,0)
        self.delete_mode = False
        self.undo_stack = QUndoStack(self)
        self.moving_nodes = {}

    def group_selected_nodes(self):
        selected_nodes = [item for item in self.selectedItems() if isinstance(item, SequenceNode)]
        if not selected_nodes:
            return

        # Calculate bounding box of selected nodes
        bounding_rect = QRectF()
        for node in selected_nodes:
            if bounding_rect.isNull():
                bounding_rect = node.sceneBoundingRect()
            else:
                bounding_rect = bounding_rect.united(node.sceneBoundingRect())

        # Create group node
        group = GroupNode()
        group.setPos(bounding_rect.topLeft() - QPointF(20, 20))
        group.width = bounding_rect.width() + 40
        group.height = bounding_rect.height() + 40
        self.addItem(group)

        # Add nodes to group
        for node in selected_nodes:
            group.add_node(node)

        self.clearSelection()
        group.setSelected(True)
        self.scene_changed.emit()

    def ungroup_nodes(self, group_node):
        for node in group_node.contained_nodes[:]:
            group_node.remove_node(node)
        self.removeItem(group_node)
        self.scene_changed.emit()

    def drawBackground(self, painter: QPainter, rect: QRectF):
        """Draws a dot grid background, inspired by Node-RED."""
        super().drawBackground(painter, rect)

        left = int(rect.left())
        right = int(rect.right())
        top = int(rect.top())
        bottom = int(rect.bottom())

        # Align to the grid
        first_left = left - (left % self.grid_size)
        first_top = top - (top % self.grid_size)

        # Draw grid points
        pen = QPen(self.grid_color)
        pen.setWidth(1)
        painter.setPen(pen)

        for x in range(first_left, right, self.grid_size):
            for y in range(first_top, bottom, self.grid_size):
                painter.drawPoint(x, y)

    def find_node_by_uuid(self, uuid_str):
        for item in self.items():
            if isinstance(item, (SequenceNode, CommentNode)) and item.uuid == uuid_str:
                return item
        return None

    def find_connection_by_uuids(self, start_uuid, end_uuid):
        for item in self.items():
            if isinstance(item, Connection):
                if item.start_port.parentItem().uuid == start_uuid and item.end_port.parentItem().uuid == end_uuid:
                    return item
        return None

    def contextMenuEvent(self, event):
        item_at_pos = self.itemAt(event.scenePos(), self.views()[0].transform())

        menu = QMenu()

        # Context menu for a node
        if isinstance(item_at_pos, GroupNode):
            ungroup_action = menu.addAction("Ungroup")
            action = menu.exec(event.screenPos())
            if action == ungroup_action:
                self.ungroup_nodes(item_at_pos)
            return

        if len(self.selectedItems()) > 1:
            group_action = menu.addAction("Group Selected")
            action = menu.exec(event.screenPos())
            if action == group_action:
                self.group_selected_nodes()
            return

        if isinstance(item_at_pos, SequenceNode):
            toggle_breakpoint_action = menu.addAction("Toggle Breakpoint")
            change_color_action = menu.addAction("Change Color...")
            menu.addSeparator()

            action = menu.exec(event.screenPos())

            if action == toggle_breakpoint_action:
                item_at_pos.toggle_breakpoint()
                self.scene_changed.emit()
            elif action == change_color_action:
                self.set_node_color(item_at_pos)
            return
        else:
            # Context menu for the scene background
            add_node_menu = menu.addMenu("Add Node")
            add_method_action = add_node_menu.addAction("Method Call (from Server Browser)")
            add_method_action.setEnabled(False)
            add_delay_action = add_node_menu.addAction(NodeType.DELAY.value)
            add_write_action = add_node_menu.addAction(NodeType.WRITE_VALUE.value)
            add_static_action = add_node_menu.addAction(NodeType.STATIC_VALUE.value)
            add_compute_action = add_node_menu.addAction(NodeType.COMPUTE.value) # NEW
            add_node_menu.addSeparator()
            add_run_sequence_action = add_node_menu.addAction(NodeType.RUN_SEQUENCE.value)
            add_node_menu.addSeparator()
            add_for_loop_action = add_node_menu.addAction(NodeType.FOR_LOOP.value)
            add_while_loop_action = add_node_menu.addAction(NodeType.WHILE_LOOP.value)
            add_node_menu.addSeparator()
            # --- FEATURE: PARALLEL EXECUTION ---
            add_fork_action = add_node_menu.addAction(NodeType.FORK.value)
            add_join_action = add_node_menu.addAction(NodeType.JOIN.value)
            add_node_menu.addSeparator()
            add_get_var_action = add_node_menu.addAction(NodeType.GET_VARIABLE.value)
            add_set_var_action = add_node_menu.addAction(NodeType.SET_VARIABLE.value)
            add_node_menu.addSeparator()
            add_python_script_action = add_node_menu.addAction(NodeType.PYTHON_SCRIPT.value)
            add_node_menu.addSeparator()
            add_mysql_write_action = add_node_menu.addAction(NodeType.MYSQL_WRITE.value)
            add_mysql_read_action = add_node_menu.addAction(NodeType.MYSQL_READ.value)
            add_node_menu.addSeparator()
            add_comment_action = add_node_menu.addAction(NodeType.COMMENT.value)

            action = menu.exec(event.screenPos())
            pos = event.scenePos()

            if action == add_delay_action:
                self.add_new_node_requested.emit(NodeType.DELAY, pos)
            elif action == add_write_action:
                self.add_new_node_requested.emit(NodeType.WRITE_VALUE, pos)
            elif action == add_static_action:
                self.add_new_node_requested.emit(NodeType.STATIC_VALUE, pos)
            elif action == add_run_sequence_action:
                self.add_new_node_requested.emit(NodeType.RUN_SEQUENCE, pos)
            elif action == add_comment_action:
                self.add_new_node_requested.emit(NodeType.COMMENT, pos)
            elif action == add_for_loop_action:
                self.add_new_node_requested.emit(NodeType.FOR_LOOP, pos)
            elif action == add_while_loop_action:
                self.add_new_node_requested.emit(NodeType.WHILE_LOOP, pos)
            elif action == add_compute_action:
                self.add_new_node_requested.emit(NodeType.COMPUTE, pos)
            elif action == add_get_var_action:
                self.add_new_node_requested.emit(NodeType.GET_VARIABLE, pos)
            elif action == add_set_var_action:
                self.add_new_node_requested.emit(NodeType.SET_VARIABLE, pos)
            elif action == add_fork_action:
                self.add_new_node_requested.emit(NodeType.FORK, pos)
            elif action == add_join_action:
                self.add_new_node_requested.emit(NodeType.JOIN, pos)
            elif action == add_python_script_action:
                self.add_new_node_requested.emit(NodeType.PYTHON_SCRIPT, pos)
            elif action == add_mysql_write_action:
                self.add_new_node_requested.emit(NodeType.MYSQL_WRITE, pos)
            elif action == add_mysql_read_action:
                self.add_new_node_requested.emit(NodeType.MYSQL_READ, pos)

    def set_node_color(self, node):
        """Opens a color dialog and sets the custom color for the given node."""
        current_color = QColor(node.config.get('custom_color', '#3c3f41'))
        color = QColorDialog.getColor(current_color, self.views()[0], "Choose Node Color")

        if color.isValid():
            node.config['custom_color'] = color.name()
            node.update() # Repaint the node
            self.scene_changed.emit()

    def set_delete_mode(self, is_active):
        self.delete_mode = is_active
        cursor = Qt.CursorShape.CrossCursor if is_active else Qt.CursorShape.ArrowCursor
        self.views()[0].setCursor(cursor)

    def mousePressEvent(self, event):
        if self.delete_mode:
            item = self.itemAt(event.scenePos(), self.views()[0].transform())
            if isinstance(item, (SequenceNode, Connection, DataConnection, CommentNode)):
                command = DeleteItemsCommand(self, [item])
                self.undo_stack.push(command)
            elif isinstance(item, (Port, DataSocket)):
                command = DeleteItemsCommand(self, [item.parentItem()])
                self.undo_stack.push(command)
            return

        item = self.itemAt(event.scenePos(), self.views()[0].transform())

        if isinstance(item, Port) and item.is_output:
            self.temp_connection = Connection(item, None, self)
            self.addItem(self.temp_connection)
        elif isinstance(item, SequenceNode) and hasattr(item, 'out_ports'):
             # Find the closest port on the Fork node
            min_dist = float('inf')
            closest_port = None
            for port in item.out_ports.values():
                dist = (event.scenePos() - port.scenePos()).manhattanLength()
                if dist < min_dist:
                    min_dist = dist
                    closest_port = port
            if closest_port:
                self.temp_connection = Connection(closest_port, None, self)
                self.addItem(self.temp_connection)
        elif isinstance(item, DataSocket) and item.is_output:
            self.temp_connection = DataConnection(item, None, self)
            self.addItem(self.temp_connection)

        super().mousePressEvent(event)

        if event.button() == Qt.MouseButton.LeftButton:
            self.moving_nodes.clear()
            for selected_item in self.selectedItems():
                if isinstance(selected_item, (SequenceNode, CommentNode)):
                    self.moving_nodes[selected_item] = selected_item.pos()

    def mouseMoveEvent(self, event):
        self.mouse_move_pos = event.scenePos()
        if self.temp_connection:
            self.temp_connection.update_path()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        # --- Snap to Grid Logic ---
        if self.moving_nodes and event.button() == Qt.MouseButton.LeftButton:
            moved_nodes = []
            old_positions = []
            new_positions = []
            for node, old_pos in self.moving_nodes.items():
                if node.pos() != old_pos:
                    moved_nodes.append(node)
                    old_positions.append(old_pos)
                    # Snap the new position to the grid
                    snapped_x = round(node.pos().x() / self.grid_size) * self.grid_size
                    snapped_y = round(node.pos().y() / self.grid_size) * self.grid_size
                    new_positions.append(QPointF(snapped_x, snapped_y))

            if moved_nodes:
                command = MoveNodesCommand(moved_nodes, old_positions, new_positions)
                self.undo_stack.push(command)
        self.moving_nodes.clear()

        if self.temp_connection:
            item = self.itemAt(event.scenePos(), self.views()[0].transform())
            if isinstance(self.temp_connection, Connection):
                valid_drop = False
                target_port = None
                if isinstance(item, Port) and not item.is_output and self.temp_connection.start_port.parentItem() != item.parentItem():
                    valid_drop = True
                    target_port = item
                elif isinstance(item, SequenceNode) and hasattr(item, 'in_ports'):
                    # Find the closest port on the Join node
                    min_dist = float('inf')
                    closest_port = None
                    for port in item.in_ports.values():
                        dist = (event.scenePos() - port.scenePos()).manhattanLength()
                        if dist < min_dist:
                            min_dist = dist
                            closest_port = port
                    if closest_port:
                        valid_drop = True
                        target_port = closest_port

                if valid_drop and target_port:
                    self.temp_connection.end_port = target_port
                    target_port.connections.append(self.temp_connection)
                    self.temp_connection.update_path()

                    if self.temp_connection.start_port.parentItem().config.get('node_.type') in [NodeType.FOR_LOOP.value, NodeType.WHILE_LOOP.value]:
                        condition = {'operator': self.temp_connection.start_port.label}
                        self.temp_connection.set_condition(condition)
                    else:
                        dialog = ConditionDialog(self.views()[0], current_condition=self.temp_connection.condition)
                        if dialog.exec():
                            self.temp_connection.set_condition(dialog.get_condition())
                        else: # FIX: No condition on cancel
                            self.temp_connection.set_condition(None)

                    self.scene_changed.emit()
                else: self.temp_connection.destroy()
            elif isinstance(self.temp_connection, DataConnection):
                valid_drop = False
                # Check against multiple input sockets
                if isinstance(item, DataSocket) and not item.is_output and self.temp_connection.start_socket.parentItem() != item.parentItem():
                     # Allow connection if the target socket doesn't already have one
                    if not item.connections:
                        valid_drop = True
                if valid_drop:
                    self.temp_connection.end_socket = item
                    item.connections.append(self.temp_connection)
                    self.temp_connection.update_path()
                    self.scene_changed.emit()
                else: self.temp_connection.destroy()
            self.temp_connection = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        item = self.itemAt(event.scenePos(), self.views()[0].transform())

        if isinstance(item, Connection):
            dialog = ConditionDialog(self.views()[0], current_condition=item.condition)
            if dialog.exec():
                item.set_condition(dialog.get_condition())
                self.scene_changed.emit()
        elif isinstance(item, SequenceNode):
            node_type = item.config.get('node_type')
            dialog = None
            if node_type == NodeType.MYSQL_WRITE.value:
                dialog = MySQLWriteNodeDialog(self.views()[0], current_config=item.config)
            elif node_type == NodeType.MYSQL_READ.value:
                dialog = MySQLReadNodeDialog(self.views()[0], current_config=item.config)
            elif node_type == NodeType.METHOD_CALL.value or node_type == NodeType.WRITE_VALUE.value:
                dialog = NodeConfigDialog(self.views()[0], current_config=item.config)
            elif node_type == NodeType.PYTHON_SCRIPT.value:
                dialog = PythonScriptDialog(self.views()[0], script=item.config.get('script', ''))
                if dialog.exec():
                    item.config['script'] = dialog.get_script()
                    self.scene_changed.emit()
                return
            elif node_type == NodeType.DELAY.value:
                delay, ok = QInputDialog.getDouble(self.views()[0], "Configure Delay", "Delay (seconds):", item.config.get('delay_seconds', 1.0), 0.1, 3600, 2)
                if ok:
                    item.config['delay_seconds'] = delay
                    self.scene_changed.emit()
                item.update_title()
                return
            elif node_type == NodeType.STATIC_VALUE.value:
                dialog = StaticValueDialog(self.views()[0], current_config=item.config)
            elif node_type == NodeType.COMPUTE.value:
                dialog = ComputeNodeDialog(self.views()[0], current_config=item.config)
            elif node_type == NodeType.SET_VARIABLE.value or node_type == NodeType.GET_VARIABLE.value:
                if hasattr(self, 'main_window'):
                    available_vars = list(self.main_window.global_variables.keys())
                    dialog = VariableNodeDialog(self.views()[0], current_config=item.config, available_variables=available_vars)
                else: # Fallback just in case
                    var_name, ok = QInputDialog.getText(self.views()[0], f"Configure {node_type}", "Variable Name:", text=item.config.get('variable_name', ''))
                    if ok and var_name:
                        item.config['variable_name'] = var_name
                        item.config['label'] = f"{node_type}: {var_name}"
                        item.update_title()
                        self.scene_changed.emit()
                    return
            elif node_type == NodeType.RUN_SEQUENCE.value:
                editor = self.views()[0]
                dialog = RunSequenceDialog(editor, item.config, editor.available_sequences, editor.current_sequence)
            elif node_type == NodeType.FOR_LOOP.value:
                iterations, ok = QInputDialog.getInt(self.views()[0], "Configure For Loop", "Iterations:", item.config.get('iterations', 1), 1, 1000000)
                if ok:
                    item.config['iterations'] = iterations
                    item.update_title()
                    self.scene_changed.emit()
                return
            elif node_type == NodeType.WHILE_LOOP.value:
                dialog = WhileLoopDialog(self.views()[0], current_config=item.config)

            if dialog and dialog.exec():
                new_config = dialog.get_config()
                if new_config:
                    item.config = new_config
                    item.update_title()
                    # After updating config, check if sockets need to be redrawn
                    if hasattr(item, 'update_sockets'):
                        item.update_sockets()
                    self.scene_changed.emit()
        super().mouseDoubleClickEvent(event)

class Minimap(QGraphicsView):
    def __init__(self, main_view):
        super().__init__(main_view.viewport())
        self.main_view = main_view
        self.setScene(self.main_view.scene)
        self._is_panning = False
        self._is_dragging_viewport = False
        self._drag_start_pos = QPointF()

        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setInteractive(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setStyleSheet("border: 1px solid #555;") # Add a border for visibility

    def get_viewport_polygon(self):
        """Calculates and returns the viewport polygon in minimap coordinates."""
        main_viewport_rect = self.main_view.viewport().rect()
        visible_scene_poly = self.main_view.mapToScene(main_viewport_rect)
        return self.mapFromScene(visible_scene_poly)

    def drawForeground(self, painter, rect):
        super().drawForeground(painter, rect)
        minimap_viewport_poly = self.get_viewport_polygon()

        painter.setPen(QPen(QColor(255, 255, 255, 128), 1))
        painter.setBrush(QBrush(QColor(255, 255, 255, 70)))
        painter.drawPolygon(minimap_viewport_poly)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            viewport_poly = self.get_viewport_polygon()
            if viewport_poly.containsPoint(event.pos(), Qt.FillRule.WindingFill):
                self._is_dragging_viewport = True
                self._drag_start_pos = event.pos()
            else:
                self._is_panning = True
                scene_pos = self.mapToScene(event.pos())
                self.main_view.centerOn(scene_pos)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._is_dragging_viewport:
            delta = event.pos() - self._drag_start_pos

            # Map the delta from minimap coordinates to scene coordinates
            # We map two points and find the difference to account for scaling/rotation
            scene_p1 = self.mapToScene(self._drag_start_pos)
            scene_p2 = self.mapToScene(event.pos())
            scene_delta = scene_p2 - scene_p1

            current_center = self.main_view.mapToScene(self.main_view.viewport().rect().center())
            new_center = current_center - scene_delta

            self.main_view.centerOn(new_center)

            # Update the start position for the next move event
            self._drag_start_pos = event.pos()

        elif self._is_panning:
            scene_pos = self.mapToScene(event.pos())
            self.main_view.centerOn(scene_pos)

        event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_panning = False
            self._is_dragging_viewport = False
            event.accept()
        else:
            super().mouseReleaseEvent(event)

class SequenceEditor(QGraphicsView):
    scene_changed = pyqtSignal()

    """The main view widget for the sequencer scene."""
    def __init__(self, *, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.scene = SequenceScene(self)
        self.scene.main_window = main_window
        self.setScene(self.scene)
        self.scene.scene_changed.connect(self.scene_changed)
        self.scene.add_new_node_requested.connect(self.on_add_new_node)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.setMouseTracking(True)

        # --- Panning and Zooming ---
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self._is_panning = False
        self._pan_start_pos = QPointF()

        self.available_sequences = []
        self.current_sequence = ""

        self.find_widget = FindWidget(self)
        self.find_widget.hide()
        self.find_widget.find_next.connect(self.find_node)
        self.find_widget.find_previous.connect(lambda text: self.find_node(text, find_next=False))
        self.find_widget.closed.connect(self.on_find_widget_closed)
        self.last_found_node = None

        # --- Minimap ---
        self.minimap = Minimap(self)
        self.horizontalScrollBar().valueChanged.connect(self.minimap.update)
        self.verticalScrollBar().valueChanged.connect(self.minimap.update)

        # --- Minimap Toggle Button ---
        self.minimap_toggle_button = QPushButton(self)
        # Using placeholder icons as the requested ones were not found
        self.icon_show_minimap = QIcon(resource_path('app/resources/icons/arrow-expand-all.png'))
        self.icon_hide_minimap = QIcon(resource_path('app/resources/icons/arrow-collapse-all.png'))
        self.minimap_toggle_button.setIcon(self.icon_hide_minimap)
        self.minimap_toggle_button.setFixedSize(30, 30)
        self.minimap_toggle_button.clicked.connect(self.toggle_minimap_visibility)
        
        self.minimap.hide()
        self.minimap_toggle_button.hide()

    def get_selected_nodes_data(self):
        """Returns a list of serialized data for all selected SequenceNode items."""
        selected_items = self.scene.selectedItems()
        return [item.serialize() for item in selected_items if isinstance(item, (SequenceNode, CommentNode))]

    def paste_nodes(self, nodes_data, paste_position):
        """Pastes nodes from serialized data onto the scene, snapping to the grid."""
        if not nodes_data:
            return

        min_x = min(node['pos']['x'] for node in nodes_data)
        min_y = min(node['pos']['y'] for node in nodes_data)

        for node_data in nodes_data:
            original_pos = node_data['pos']
            offset_x = original_pos['x'] - min_x
            offset_y = original_pos['y'] - min_y

            # Calculate the new position and snap it to the grid
            raw_x = paste_position.x() + offset_x
            raw_y = paste_position.y() + offset_y
            grid_size = self.scene.grid_size
            snapped_x = round(raw_x / grid_size) * grid_size
            snapped_y = round(raw_y / grid_size) * grid_size
            new_pos = QPointF(snapped_x, snapped_y)

            new_config = node_data['config']

            command = AddNodeCommand(self.scene, new_config, new_pos)
            self.scene.undo_stack.push(command)

        logging.info(f"Pasted {len(nodes_data)} nodes.")

    def mousePressEvent(self, event):
        """Handles middle-mouse button panning."""
        if event.button() == Qt.MouseButton.MiddleButton:
            self._is_panning = True
            self._pan_start_pos = event.pos()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """Updates the view position when panning and handles live data probes."""
        if self._is_panning:
            delta = event.pos() - self._pan_start_pos
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            self._pan_start_pos = event.pos()
            event.accept()
            return

        # --- Live Data Probe Logic ---
        main_window = self.window()
        if not hasattr(main_window, 'running_sequences'):
             super().mouseMoveEvent(event)
             return

        current_engine = main_window.running_sequences.get(self.current_sequence)

        if current_engine and current_engine.debug_state == DebugState.PAUSED:
            item = self.itemAt(event.pos())
            if isinstance(item, DataConnection):
                value = current_engine.data_connection_values.get(item.uuid, "N/A")
                tooltip_text = f"Last Value: {value}"
                QToolTip.showText(event.globalPos(), tooltip_text, self)
            else:
                QToolTip.hideText()
        else:
            QToolTip.hideText()

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """Stops the panning operation."""
        if event.button() == Qt.MouseButton.MiddleButton and self._is_panning:
            self._is_panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def wheelEvent(self, event):
        """Zooms the view with Ctrl + Mouse Wheel."""
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            if event.angleDelta().y() > 0:
                self.zoom_in()
            else:
                self.zoom_out()
        else:
            super().wheelEvent(event)

    def zoom_in(self):
        """Scales the view up by 20%."""
        self.scale(1.2, 1.2)
        if self.minimap:
            self.minimap.update()

    def zoom_out(self):
        """Scales the view down by 20%."""
        self.scale(1 / 1.2, 1 / 1.2)
        if self.minimap:
            self.minimap.update()

    def reset_zoom(self):
        """Resets the view's transformation to the default state."""
        self.setTransform(QTransform())

    def delete_selected_items(self):
        """Deletes the currently selected nodes and connections."""
        selected_items = self.scene.selectedItems()
        if selected_items:
            top_level_items = [item for item in selected_items if not item.parentItem() in selected_items]
            command = DeleteItemsCommand(self.scene, top_level_items)
            self.scene.undo_stack.push(command)
            return True
        return False

    def toggle_minimap_visibility(self):
        """Shows or hides the minimap and updates the toggle button's icon."""
        if self.minimap.isVisible():
            self.minimap.hide()
            self.minimap_toggle_button.setIcon(self.icon_show_minimap)
        else:
            self.minimap.show()
            self.minimap_toggle_button.setIcon(self.icon_hide_minimap)

    def resizeEvent(self, event):
        """Ensure widgets stay in their correct positions on resize."""
        super().resizeEvent(event)
        if self.find_widget:
            self.find_widget.move(self.width() - self.find_widget.width() - 10, 10)

        # Position minimap and its toggle button
        if self.minimap and self.minimap_toggle_button:
            minimap_size = 200
            margin = 10
            button_size = self.minimap_toggle_button.height()

            # Position minimap in bottom-right corner
            minimap_x = self.width() - minimap_size - margin
            minimap_y = self.height() - minimap_size - margin
            self.minimap.setGeometry(minimap_x, minimap_y, minimap_size, minimap_size)
            self.minimap.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

            # Position toggle button just above the minimap
            button_x = self.width() - button_size - margin
            button_y = minimap_y - button_size - (margin / 2)
            self.minimap_toggle_button.move(int(button_x), int(button_y))

    def show_find_widget(self):
        """Shows and focuses the find widget in the top-right corner of the tab content area."""
        from PyQt6.QtCore import QPoint
        top_left = self.viewport().mapToGlobal(QPoint(0, 0))
        parent_top_left = self.mapToGlobal(QPoint(0, 0))
        offset_x = 10
        offset_y = 10
        x = offset_x
        y = offset_y
        self.find_widget.setParent(self.viewport())
        self.find_widget.show_and_focus(pos=(x, y))
        self.setDragMode(QGraphicsView.DragMode.NoDrag)

    def on_find_widget_closed(self):
        """Restores normal operation when the find widget is closed."""
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.last_found_node = None
        self.scene.clearSelection()

    def find_node(self, text, find_next=True):
        """Finds and selects the next/previous node matching the text."""
        search_term = text.lower()
        nodes = [item for item in self.scene.items() if isinstance(item, (SequenceNode, CommentNode))]

        if not find_next:
            nodes.reverse()

        start_index = 0
        if self.last_found_node and self.last_found_node in nodes:
            start_index = nodes.index(self.last_found_node) + 1

        for i in range(len(nodes)):
            index = (start_index + i) % len(nodes)
            node = nodes[index]
            if isinstance(node, SequenceNode):
                if search_term in node.config.get('label', '').lower():
                    self.scene.clearSelection()
                    node.setSelected(True)
                    self.centerOn(node)
                    self.last_found_node = node
                    return
            elif isinstance(node, CommentNode):
                if search_term in node.toPlainText().lower():
                    self.scene.clearSelection()
                    node.setSelected(True)
                    self.centerOn(node)
                    self.last_found_node = node
                    return

        self.last_found_node = None

    def select_all_nodes(self):
        """Selects all nodes and connections in the scene."""
        for item in self.scene.items():
            if isinstance(item, (SequenceNode, Connection, DataConnection, CommentNode)):
                item.setSelected(True)

    def set_available_sequences(self, names, current_name):
        self.available_sequences = names
        self.current_sequence = current_name

    def update_node_state(self, node_uuid, state):
        node = self.scene.find_node_by_uuid(node_uuid)
        if node:
            node.set_state(state)

    def update_connection_state(self, start_uuid, end_uuid, state):
        connection = self.scene.find_connection_by_uuids(start_uuid, end_uuid)
        if connection:
            connection.set_state(state)

    def reset_visual_states(self):
        for item in self.scene.items():
            if isinstance(item, (SequenceNode, Connection, DataConnection)):
                if hasattr(item, 'set_state'):
                    item.set_state("idle")

    def add_node(self, config):
        """Adds a pre-configured node (typically a Method Call from the server tree)."""
        config['node_type'] = NodeType.METHOD_CALL.value
        position = self.mapToScene(self.viewport().rect().center())

        # Snap new node position to grid
        grid_size = self.scene.grid_size
        snapped_x = round(position.x() / grid_size) * grid_size
        snapped_y = round(position.y() / grid_size) * grid_size
        snapped_pos = QPointF(snapped_x, snapped_y)
        command = AddNodeCommand(self.scene, config, snapped_pos)
        self.scene.undo_stack.push(command)

    def on_add_new_node(self, node_type: NodeType, position: QPointF):
        """Handles the request to add a new, non-method-call node."""
        config = {'node_type': node_type.value}

        if node_type == NodeType.DELAY:
            config['label'] = "Delay"
            config['delay_seconds'] = 1.0
        elif node_type == NodeType.WRITE_VALUE:
            config['label'] = "Write Value"
            config['node_id'] = ""
            config['has_argument'] = True
        elif node_type == NodeType.STATIC_VALUE:
            config['label'] = "Static Value"
            config['static_value'] = "0"
        elif node_type == NodeType.COMPUTE.value: # NEW
            config['label'] = "Compute"
            config['expression'] = ""
        elif node_type == NodeType.SET_VARIABLE.value:
            config['label'] = "Set Variable"
            config['variable_name'] = "my_var"
        elif node_type == NodeType.GET_VARIABLE.value:
            config['label'] = "Get Variable"
            config['variable_name'] = "my_var"
        elif node_type == NodeType.FORK.value:
            config['label'] = "Fork"
        elif node_type == NodeType.JOIN.value:
            config['label'] = "Join"
        elif node_type == NodeType.RUN_SEQUENCE:
            dialog = RunSequenceDialog(self, None, self.available_sequences, self.current_sequence)
            if not dialog.exec(): return
            new_config = dialog.get_config()
            if not new_config: return
            config.update(new_config)
        elif node_type == NodeType.COMMENT:
            config['text'] = "Comment"
        elif node_type == NodeType.FOR_LOOP:
            config['label'] = "For Loop"
            config['iterations'] = 1
        elif node_type == NodeType.WHILE_LOOP:
            config['label'] = "While (!True)"
            config['while_negate_condition'] = True
            config['while_condition_value'] = "True"
        elif node_type == NodeType.PYTHON_SCRIPT:
            config['label'] = "Python Script"
            config['script'] = "# INPUT is available as a variable\n# Set the output value using: output = ..."
        elif node_type == NodeType.MYSQL_WRITE:
            config['label'] = "MySQL Write"
            config['table_name'] = "my_table"
            config['mappings'] = {} # {'socket_name': 'column_name'}
            config['inputs'] = ['input1', 'input2'] # Default inputs
        elif node_type == NodeType.MYSQL_READ:
            config['label'] = "MySQL Read"
            config['query'] = "SELECT * FROM my_table"

        command = AddNodeCommand(self.scene, config, position)
        self.scene.undo_stack.push(command)

    def set_delete_mode(self, is_active):
        self.scene.set_delete_mode(is_active)

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Delete:
            self.delete_selected_items()
        else:
            super().keyPressEvent(event)

    def serialize(self):
        """Serializes the scene to a dictionary."""
        nodes = []
        exec_connections = []
        data_connections = []
        groups = []
        for item in self.scene.items():
            if isinstance(item, (SequenceNode, CommentNode)):
                nodes.append(item.serialize())
            elif isinstance(item, GroupNode):
                groups.append(item.serialize())
            elif isinstance(item, Connection):
                serialized_conn = item.serialize()
                if serialized_conn:
                    exec_connections.append(serialized_conn)
            elif isinstance(item, DataConnection):
                serialized_conn = item.serialize()
                if serialized_conn:
                    data_connections.append(serialized_conn)
        return {'nodes': nodes, 'exec_connections': exec_connections, 'data_connections': data_connections, 'groups': groups}

    def load_data(self, data):
        """Loads a scene from a dictionary."""
        self.scene.clear()
        self.scene.undo_stack.clear()
        nodes_map = {}

        if 'nodes' in data:
            for node_data in data['nodes']:
                node_type = node_data['config'].get('node_type')
                if node_type == NodeType.COMMENT.value:
                    node = CommentNode(node_data['config']['text'], node_data['uuid'])
                else:
                    node = SequenceNode(node_data['config'], node_data['uuid'])
                    node.has_breakpoint = node_data.get('has_breakpoint', False)
                node.setPos(QPointF(node_data['pos']['x'], node_data['pos']['y']))
                self.scene.addItem(node)
                nodes_map[node_data['uuid']] = node

        if 'groups' in data:
            for group_data in data['groups']:
                group = GroupNode(group_data['title'], group_data['uuid'])
                group.setPos(QPointF(group_data['pos']['x'], group_data['pos']['y']))
                group.width = group_data['size']['width']
                group.height = group_data['size']['height']
                self.scene.addItem(group)
                for node_uuid in group_data['contained_nodes']:
                    if node_uuid in nodes_map:
                        group.add_node(nodes_map[node_uuid])

        if 'exec_connections' in data:
            for conn_data in data['exec_connections']:
                start_node = nodes_map.get(conn_data['start_node_uuid'])
                end_node = nodes_map.get(conn_data['end_node_uuid'])
                if start_node and end_node:
                    start_port = start_node.out_port
                    if start_node.config.get('node_type') in [NodeType.FOR_LOOP.value, NodeType.WHILE_LOOP.value]:
                        if conn_data.get('condition', {}).get('operator') == 'Loop Body':
                            start_port = start_node.out_port_loop_body
                        else:
                            start_port = start_node.out_port_finished

                    connection = Connection(start_port, end_node.in_port, self.scene)
                    if conn_data.get('condition'):
                        connection.set_condition(conn_data['condition'])
                    self.scene.addItem(connection)

        if 'data_connections' in data:
            for conn_data in data['data_connections']:
                start_node = nodes_map.get(conn_data['start_node_uuid'])
                end_node = nodes_map.get(conn_data['end_node_uuid'])
                if start_node and end_node:
                    end_socket = None
                    # MODIFIED: Find correct socket by label for multi-input nodes
                    socket_label = conn_data.get('end_socket_label')
                    if socket_label and hasattr(end_node, 'data_in_sockets') and end_node.data_in_sockets:
                        end_socket = end_node.data_in_sockets.get(socket_label)
                    elif hasattr(end_node, 'data_in_socket'): # Fallback for older/single-input nodes
                        end_socket = end_node.data_in_socket

                    if start_node.data_out_socket and end_socket:
                        connection = DataConnection(start_node.data_out_socket, end_socket, self.scene, conn_data.get('uuid'))
                        connection.update_path()
                        self.scene.addItem(connection)
