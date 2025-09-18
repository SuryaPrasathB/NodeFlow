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
                             QComboBox, QGraphicsProxyWidget, QToolTip)
from PyQt6.QtCore import Qt, QRectF, QPointF, pyqtSignal, QObject, QPropertyAnimation
from PyQt6.QtGui import (QPainter, QColor, QBrush, QPen, QPainterPath, QKeyEvent, 
                         QPainterPathStroker, QUndoCommand, QUndoStack, QFont, QTransform, QAction)

# --- Local Imports ---
from .condition_dialog import ConditionDialog
from .node_config_dialog import NodeConfigDialog
from .compute_node_dialog import ComputeNodeDialog
from .error_dialog import show_error_message
from app.ui.widgets.find_widget import FindWidget

class DebugState(Enum):
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
    # --- FEATURE: PARALLEL EXECUTION ---
    FORK = "Fork"
    JOIN = "Join"
    # --- FEATURE: GLOBAL VARIABLES ---
    SET_VARIABLE = "Set Variable"
    GET_VARIABLE = "Get Variable"

class CommentNode(QGraphicsTextItem):
    def __init__(self, text, uuid_str=None):
        super().__init__(text)
        self.uuid = uuid_str or str(uuid.uuid4())
        self.setFlag(QGraphicsObject.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsObject.GraphicsItemFlag.ItemIsSelectable)
        self.setFlag(QGraphicsObject.GraphicsItemFlag.ItemIsFocusable)
        self.setTextInteractionFlags(Qt.TextEditorInteraction)
        self.setDefaultTextColor(QColor("#FFFFFF"))
        font = QFont()
        font.setPointSize(12)
        self.setFont(font)

    def serialize(self):
        return {
            'uuid': self.uuid,
            'config': {'node_type': NodeType.COMMENT.value, 'text': self.toPlainText()},
            'pos': {'x': self.pos().x(), 'y': self.pos().y()}
        }

class WhileLoopDialog(QDialog):
    def __init__(self, parent=None, current_config=None):
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
        self.config['while_negate_condition'] = (self.condition_type_combo.currentText() == "is not")
        self.config['while_condition_value'] = self.value_input.text()
        negate_str = "!" if self.config['while_negate_condition'] else ""
        self.config['label'] = f"While ({negate_str}{self.config['while_condition_value']})"
        return self.config

    def get_config(self):
        self.config['while_negate_condition'] = (self.condition_type_combo.currentText() == "is not")
        self.config['while_condition_value'] = self.value_input.text()
        # Update the label for the node title
        negate_str = "!" if self.config['while_negate_condition'] else ""
        self.config['label'] = f"While ({negate_str}{self.config['while_condition_value']})"
        return self.config

class RunSequenceDialog(QDialog):
    """A dialog for configuring the RunSequenceNode."""
    def __init__(self, parent=None, current_config=None, available_sequences=None, current_sequence=None):
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
        """Returns the updated configuration for the node."""
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
        self.config['static_value'] = self.value_input.text()
        self.config['label'] = f"Value: {self.config['static_value']}"
        return self.config

class WriteValueDialog(QDialog):
    """A simple dialog for configuring the WriteValueNode."""
    def __init__(self, parent=None, current_config=None):
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
        self.config['node_id'] = self.node_id_input.text()
        self.config['value_to_write'] = self.value_input.text()
        return self.config
    
class Port(QGraphicsObject):
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

    def boundingRect(self): return QRectF(-self.radius, -self.radius, 2 * self.radius, 2 * self.radius)
    def paint(self, painter, option, widget=None):
        painter.setBrush(QBrush(QColor("#5a98d1")))
        painter.setPen(QPen(Qt.GlobalColor.white, 1))
        painter.drawEllipse(-self.radius, -self.radius, 2 * self.radius, 2 * self.radius)
    def itemChange(self, change, value):
        if change == QGraphicsObject.GraphicsItemChange.ItemScenePositionHasChanged:
            for conn in self.connections: conn.update_path()
        return value

class Connection(QGraphicsPathItem):
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
        stroker = QPainterPathStroker(); stroker.setWidth(10)
        return stroker.createStroke(self.path())

    def set_state(self, new_state):
        self.state = new_state; self.update()

    def paint(self, painter, option, widget=None):
        color = "#f0e68c" if self.state == "active" else "#ffffff"
        width = 3 if self.state == "active" else 2
        pen = QPen(QColor(color), width)
        if self.isSelected(): pen.setColor(QColor("#ffc400"))
        painter.setPen(pen); painter.drawPath(self.path())

    def set_condition(self, condition):
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
        if self.start_port and self in self.start_port.connections: self.start_port.connections.remove(self)
        if self.end_port and self in self.end_port.connections: self.end_port.connections.remove(self)
        self._scene.removeItem(self)

    def serialize(self):
        if not self.start_port or not self.end_port: return None
        return {'start_node_uuid': self.start_port.parentItem().uuid, 'end_node_uuid': self.end_port.parentItem().uuid, 'condition': self.condition}

class SequenceEngine(QObject):
    execution_paused = pyqtSignal(str, str) # sequence_name, node_uuid
    
    """
    The backend logic engine that executes a sequence graph. It is now decoupled
    from the UI and emits signals with identifiers for MainWindow to route.
    """
    execution_finished = pyqtSignal(str, bool)
    node_state_changed = pyqtSignal(str, str, str)  # Emits sequence_name, node_uuid, state
    connection_state_changed = pyqtSignal(str, str, str, str)  # Emits sequence_name, start_uuid, end_uuid, state

    def __init__(self, opcua_logic, async_runner, global_variables):
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
        logging.debug(f"RESUME BUTTON CLICKED. Current state: {self.debug_state}")
        if self.debug_state == DebugState.PAUSED:
            self._pause_event.set() # Release the pause

    def step_over(self):
        logging.debug("STEP OVER BUTTON CLICKED. Current state: {}".format(self.debug_state))
        if self.debug_state == DebugState.PAUSED:
            self._step_into = False
            self._step_event.set() # Allow one step
            self._pause_event.set()

    def step_into(self):
        logging.debug("STEP INTO BUTTON CLICKED. Current state: {}".format(self.debug_state))
        if self.debug_state == DebugState.PAUSED:
            self._step_into = True
            self._step_event.set() # Allow one step, including sub-sequences
            self._pause_event.set()

    def run(self, sequence_name, all_sequences, loop=False):
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
        if self.debug_state != DebugState.IDLE:
            logging.info("Stop requested for sequence execution.")
            self.is_looping = False
            self._stop_requested = True
            self.resume() # In case we are paused

    async def _run_main_loop(self, start_node, sequence_data):
        """The top-level loop that handles the 'loop' toggle."""
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
        """Executes a given sequence graph. Can be called recursively for sub-sequences."""
        active_connection_data = None
        current_node = start_node
        
        node_map = {node_data['uuid']: node_data for node_data in sequence_data.get('nodes', [])}

        while current_node and not self._stop_requested:
            # --- THIS IS THE CORE DEBUGGING LOGIC ---
            # Check for breakpoint on the current node
            if current_node.get('has_breakpoint') and self._pause_event.is_set():
                if not (is_sub_sequence and not self._step_into):
                    self.debug_state = DebugState.PAUSED
                    self._pause_event.clear() # Prepare to pause
                    self.execution_paused.emit(sequence_name, current_node['uuid'])
            
            # Wait here if paused
            await self._pause_event.wait()
            
            # If we were paused and are now stepping, clear the step event
            if self.debug_state == DebugState.PAUSED:
                self.debug_state = DebugState.RUNNING
                await self._step_event.wait()
                self._step_event.clear()
            # --- END OF DEBUGGING LOGIC ---
            
            if active_connection_data:
                self.connection_state_changed.emit(
                    sequence_name,
                    active_connection_data['start_node_uuid'],
                    active_connection_data['end_node_uuid'],
                    "idle"
                )
                await asyncio.sleep(0.1)

            self.node_state_changed.emit(sequence_name, current_node['uuid'], "running")
            
            value, success = await self.execute_node(current_node, self._step_into)

            if not success:
                # Handle the special case for Join nodes waiting for other branches.
                if value == "WAITING_FOR_JOIN":
                    # This branch is done, but it's not a failure.
                    logging.debug(f"Branch execution paused, waiting for join at node {current_node['uuid']}.")
                    return None, True # Return success so the gather doesn't fail
                else:
                    # It's a real failure.
                    self.node_state_changed.emit(sequence_name, current_node['uuid'], "failed")
                    return None, False
            
            self.node_state_changed.emit(sequence_name, current_node['uuid'], "success")
            await asyncio.sleep(0.2)
            
            next_node_uuid, active_connection_data = self.find_next_node_and_connection(current_node, value, sequence_data)

            if active_connection_data:
                self.connection_state_changed.emit(
                    sequence_name,
                    active_connection_data['start_node_uuid'],
                    active_connection_data['end_node_uuid'],
                    "active"
                )
                await asyncio.sleep(0.2)
            
            current_node = node_map.get(next_node_uuid) if next_node_uuid else None
        
        if active_connection_data:
            self.connection_state_changed.emit(
                sequence_name,
                active_connection_data['start_node_uuid'],
                active_connection_data['end_node_uuid'],
                "idle"
            )
            
        return value, True

    async def execute_node(self, node_data, step_into = False):
        node_type = node_data['config'].get('node_type')

        if node_type == NodeType.METHOD_CALL.value:
            return await self.execute_method_call_node(node_data)
        elif node_type == NodeType.DELAY.value:
            return await self.execute_delay_node(node_data)
        elif node_type == NodeType.WRITE_VALUE.value:
            return await self.execute_write_value_node(node_data)
        elif node_type == NodeType.STATIC_VALUE.value:
            return await self.execute_static_value_node(node_data)
        elif node_type == NodeType.RUN_SEQUENCE.value:
            return await self.execute_run_sequence_node(node_data, step_into)
        elif node_type == NodeType.FOR_LOOP.value:
            return await self.execute_for_loop_node(node_data)
        elif node_type == NodeType.WHILE_LOOP.value:
            return await self.execute_while_loop_node(node_data)
        elif node_type == NodeType.COMPUTE.value:
            return await self.execute_compute_node(node_data)
        elif node_type == NodeType.SET_VARIABLE.value:
            return await self.execute_set_variable_node(node_data)
        elif node_type == NodeType.GET_VARIABLE.value:
            return await self.execute_get_variable_node(node_data)
        elif node_type == NodeType.FORK.value:
            return await self.execute_fork_node(node_data)
        elif node_type == NodeType.JOIN.value:
            return await self.execute_join_node(node_data)
        else:
            logging.error(f"Unknown node type '{node_type}' for node '{node_data['config']['label']}'")
            return None, False

    async def execute_compute_node(self, node_data):
        """Evaluates a mathematical or logical expression."""
        try:
            config = node_data['config']
            expression = config.get('expression')
            if not expression:
                raise ValueError("Compute node has no expression.")

            local_vars = {}
            current_sequence_data = self.all_sequences[self.current_sequence_name]
            data_connections = current_sequence_data.get('data_connections', [])

            # Find all connections ending at this compute node to gather inputs
            for conn in data_connections:
                if conn['end_node_uuid'] == node_data['uuid']:
                    input_label = conn.get('end_socket_label')  # 'A', 'B', 'C'
                    source_uuid = conn['start_node_uuid']
                    
                    if input_label and source_uuid in self.execution_context:
                        local_vars[input_label] = self.execution_context[source_uuid]
                    else:
                        logging.warning(f"Could not find pre-computed value for input '{input_label}' from node '{source_uuid}'.")
                        return None, False
            
            logging.info(f"Evaluating expression: '{expression}' with inputs: {local_vars}")
            
            # Safe eval environment
            # We allow the local_vars (A, B, C) and built-in functions that are generally safe.
            result = eval(expression, {"__builtins__": None}, local_vars)
            
            logging.info(f"Expression result: {result}")
            self.execution_context[node_data['uuid']] = result
            return result, True

        except Exception as e:
            logging.error(f"Failed to execute compute node '{node_data['config'].get('label', 'N/A')}': {e}")
            return None, False

    async def execute_while_loop_node(self, node_data):
        """Executes the while loop based on a configurable condition."""
        current_sequence_data = self.all_sequences[self.current_sequence_name]
        node_map = {n['uuid']: n for n in current_sequence_data['nodes']}

        # Get loop configuration from the node
        negate_condition = node_data['config'].get('while_negate_condition', True)
        condition_target_str = node_data['config'].get('while_condition_value', '')

        # Find the node connected to the "Loop Body" output
        loop_body_start_node_uuid, _ = self.find_next_node_and_connection(node_data, "Loop Body", current_sequence_data)
        if not loop_body_start_node_uuid:
            logging.warning("While Loop has no 'Loop Body' connected.")
            return "Finished", True

        loop_start_node = node_map.get(loop_body_start_node_uuid)

        # Find the source of the data input to re-evaluate it on each iteration
        source_node_uuid = next((conn['start_node_uuid'] for conn in current_sequence_data.get('data_connections', []) if conn['end_node_uuid'] == node_data['uuid']), None)
        if not source_node_uuid:
            logging.error("While Loop requires a data input connection for its condition.")
            return None, False

        source_node_data = node_map.get(source_node_uuid)
        if not source_node_data:
            logging.error(f"Could not find the source node ({source_node_uuid}) for the While Loop condition.")
            return None, False

        # Main loop execution
        iteration_count = 0
        max_iterations = 1000  # Safety break
        while iteration_count < max_iterations:
            if self._stop_requested: break

            # Re-evaluate the condition by re-executing the source node
            self.node_state_changed.emit(self.current_sequence_name, source_node_data['uuid'], "running")
            live_value, success = await self.execute_node(source_node_data)
            self.node_state_changed.emit(self.current_sequence_name, source_node_data['uuid'], "success" if success else "failed")
            
            if not success:
                logging.error("Failed to evaluate While Loop condition.")
                return None, False

            # Convert the configured target value to the same type as the live value for proper comparison
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

            # Check if we should continue looping
            if negate_condition: # Loop while "is not" - break when they match
                if is_match: break
            else: # Loop while "is" - break when they don't match
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
        iterations = int(node_data['config'].get('iterations', 1))
        
        # Find the node connected to the "Loop Body" output
        loop_body_start_node_uuid, _ = self.find_next_node_and_connection(node_data, "Loop Body", self.all_sequences[self.current_sequence_name])
        
        if not loop_body_start_node_uuid:
            logging.warning("For Loop has no 'Loop Body' connected.")
        else:
            node_map = {n['uuid']: n for n in self.all_sequences[self.current_sequence_name]['nodes']}
            for i in range(iterations):
                if self._stop_requested:
                    break
                
                logging.info(f"For Loop iteration {i + 1}/{iterations}")
                
                # Execute the graph starting from the loop body node
                loop_start_node = node_map.get(loop_body_start_node_uuid)
                if loop_start_node:
                    # This is a simplified implementation. A more robust solution would trace the graph.
                    await self._execute_graph(self.current_sequence_name, loop_start_node, self.all_sequences[self.current_sequence_name], is_sub_sequence=True)

        return "Finished", True

    async def execute_run_sequence_node(self, node_data, step_into=False):
        """Executes a sub-sequence."""
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
        try:
            config = node_data['config']
            variable_name = config.get('variable_name')
            if not variable_name:
                raise ValueError("Variable name is not configured.")

            # Resolve the input value. This reuses the logic for finding
            # the data connection and getting the value from the execution context.
            value_to_set = await self.resolve_argument_value(node_data, self.current_sequence_name)

            # --- FEATURE: GLOBAL VARIABLES ---
            # The 'global_variables' dict is passed in from MainWindow
            self.global_variables[variable_name] = value_to_set

            logging.info(f"Set global variable '{variable_name}' to: {value_to_set}")
            return True, True # Continue execution, no output value
        except Exception as e:
            logging.error(f"Failed to execute Set Variable node: {e}")
            return None, False

    async def execute_get_variable_node(self, node_data):
        try:
            config = node_data['config']
            variable_name = config.get('variable_name')
            if not variable_name:
                raise ValueError("Variable name is not configured.")

            # --- FEATURE: GLOBAL VARIABLES ---
            value = self.global_variables.get(variable_name)
            if value is None:
                logging.warning(f"Global variable '{variable_name}' not found. Returning None.")

            # Put the retrieved value into the context for downstream data nodes
            self.execution_context[node_data['uuid']] = value

            logging.info(f"Retrieved global variable '{variable_name}'. Value: {value}")
            return value, True
        except Exception as e:
            logging.error(f"Failed to execute Get Variable node: {e}")
            return None, False

    async def execute_fork_node(self, node_data):
        """Finds all outgoing execution paths and runs them concurrently."""
        sequence_data = self.all_sequences[self.current_sequence_name]
        node_map = {n['uuid']: n for n in sequence_data['nodes']}

        # Find all branches starting from this fork node
        branches = []
        for conn_data in sequence_data.get('exec_connections', []):
            if conn_data['start_node_uuid'] == node_data['uuid']:
                next_node_uuid = conn_data['end_node_uuid']
                if next_node_uuid in node_map:
                    branches.append(node_map[next_node_uuid])

        if not branches:
            logging.warning(f"Fork node '{node_data['uuid']}' has no outgoing connections.")
            return True, True # Forking nothing is a success

        logging.info(f"Forking execution into {len(branches)} branches.")

        # Create a task for each branch
        tasks = []
        for start_node_of_branch in branches:
            task = asyncio.create_task(
                self._execute_graph(self.current_sequence_name, start_node_of_branch, sequence_data, is_sub_sequence=True)
            )
            tasks.append(task)

        # Wait for all forked branches to complete
        await asyncio.gather(*tasks)

        logging.info(f"All forked branches from '{node_data['uuid']}' have completed.")

        # A Fork node itself doesn't pass a value, it just splits execution.
        # It signals completion to the _next_ node, which is typically a Join.
        # However, the standard model is that the branches lead to a Join,
        # and the Join node is what continues the main sequence flow.
        # So, the Fork node's job is done after gathering the tasks.
        return True, True

    async def execute_join_node(self, node_data):
        """Waits for all incoming execution paths to complete before continuing."""
        join_uuid = node_data['uuid']

        # We use the execution context to store the state of the join
        if join_uuid not in self.execution_context:
            # First time hitting this join node in this run
            num_incoming_connections = sum(1 for conn in self.all_sequences[self.current_sequence_name].get('exec_connections', []) if conn['end_node_uuid'] == join_uuid)
            self.execution_context[join_uuid] = {
                'arrivals': 1,
                'expected': num_incoming_connections
            }
            logging.debug(f"Join node '{join_uuid}' first arrival. Expecting {num_incoming_connections} total.")
        else:
            # Subsequent arrival
            self.execution_context[join_uuid]['arrivals'] += 1
            logging.debug(f"Join node '{join_uuid}' arrival #{self.execution_context[join_uuid]['arrivals']}.")

        context = self.execution_context[join_uuid]
        if context['arrivals'] < context['expected']:
            # Not all branches have arrived yet, so we stop this path of execution.
            # We return a special value to indicate this is not a failure, but a pause.
            logging.debug(f"Join node '{join_uuid}' waiting for more arrivals.")
            return "WAITING_FOR_JOIN", False # Special case: stop this branch, but don't fail the sequence
        else:
            # All branches have arrived.
            logging.info(f"Join node '{join_uuid}' has received all {context['expected']} arrivals. Continuing execution.")
            # Reset for potential future loops
            del self.execution_context[join_uuid]
            return True, True

    def find_next_node_and_connection(self, current_node_data, result, sequence_data):
        exec_connections = sequence_data.get('exec_connections', [])
        for conn_data in exec_connections:
            if conn_data['start_node_uuid'] == current_node_data['uuid']:
                if self.evaluate_condition(conn_data, result):
                    return conn_data['end_node_uuid'], conn_data
        return None, None

    def evaluate_condition(self, connection_data, result):
        """
        Evaluates the condition on a connection, supporting both simple
        comparisons and custom Python expressions.
        """
        condition = connection_data.get('condition')
        if not condition:
            return True

        # --- NEW: Handle expression-based conditions ---
        if condition.get('type') == 'expression':
            expression = condition.get('expression')
            if not expression:
                return True  # An empty expression is treated as a pass-through
            try:
                # Safely evaluate the expression with the input value
                local_scope = {'INPUT': result}
                eval_result = eval(expression, {"__builtins__": {}}, local_scope)
                return bool(eval_result)
            except Exception as e:
                logging.error(f"Error evaluating condition expression '{expression}': {e}")
                return False  # Fail-safe

        # --- Fallback to simple comparison for old format or explicit simple type ---
        op = condition.get('operator')
        if op == 'No Condition':
            return True
            
        # Special handling for For/While Loop outputs
        if op in ["Loop Body", "Finished"]:
            return result == op

        # Handle conditions that don't have a 'value' key
        if op == "is True":
            return result is True
        if op == "is False":
            return result is False

        if 'value' not in condition:
            logging.error(f"Condition '{op}' requires a 'value' but none was found in {condition}.")
            return False 

        val_str = condition['value']
        try:
            if isinstance(result, bool):
                if val_str.lower() in ['true', '1', 't']: val = True
                elif val_str.lower() in ['false', '0', 'f']: val = False
                else: val = val_str
            elif isinstance(result, (int, float)):
                 val = type(result)(val_str)
            else:
                 val = val_str
        except (ValueError, TypeError): 
            val = val_str

        if op == "==": return result == val
        if op == "!=": return result != val
        if op == ">": return result > val
        if op == "<": return result < val
        if op == ">=": return result >= val
        if op == "<=": return result <= val
        
        return False

    def find_start_node(self, sequence_data):
        nodes = sequence_data.get('nodes', [])
        if not nodes: return None
        
        end_node_uuids = {conn['end_node_uuid'] for conn in sequence_data.get('exec_connections', [])}
        for node_data in nodes:
            if node_data['uuid'] not in end_node_uuids:
                return node_data
        return None

class Port(QGraphicsObject):
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

    def boundingRect(self): return QRectF(-self.radius, -self.radius, 2 * self.radius, 2 * self.radius)
    def paint(self, painter, option, widget=None):
        painter.setBrush(QBrush(QColor("#5a98d1")))
        painter.setPen(QPen(Qt.GlobalColor.white, 1))
        painter.drawEllipse(-self.radius, -self.radius, 2 * self.radius, 2 * self.radius)
    def itemChange(self, change, value):
        if change == QGraphicsObject.GraphicsItemChange.ItemScenePositionHasChanged:
            for conn in self.connections: conn.update_path()
        return value

class Connection(QGraphicsPathItem):
    """A visual execution connection drawn as an automatic, smooth S-curve."""
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
        stroker = QPainterPathStroker()
        stroker.setWidth(10)
        return stroker.createStroke(self.path())

    def set_state(self, new_state):
        self.state = new_state
        self.update()

    def paint(self, painter, option, widget=None):
        color = "#f0e68c" if self.state == "active" else "#ffffff"
        width = 3 if self.state == "active" else 2
        pen = QPen(QColor(color), width)

        if self.isSelected():
            pen.setColor(QColor("#ffc400"))
        
        painter.setPen(pen)
        painter.drawPath(self.path())

    def set_condition(self, condition):
        self.condition = condition
        label_text = ''
        if self.condition:
            if self.condition.get('type') == 'expression':
                expr = self.condition.get('expression', '')
                if len(expr) > 20:
                    expr = expr[:17] + '...'
                label_text = f"fx: {expr}" if expr else ""
            else: 
                op = self.condition.get('operator', '')
                if op != "No Condition":
                    label_text = op
        
        self.condition_label.setPlainText(label_text)
        self.update_path()


    def update_path(self):
        path = QPainterPath()
        start_pos = self.start_port.scenePos()
        # FIX: Check if end_port exists before trying to access its scenePos
        end_pos = self.end_port.scenePos() if self.end_port else self._scene.mouse_move_pos
        
        path.moveTo(start_pos)

        # Automatic S-curve calculation
        dx = end_pos.x() - start_pos.x()
        dy = end_pos.y() - start_pos.y()
        
        # A fixed offset for the control points to create a gentle curve
        offset = 50.0
        ctrl1 = QPointF(start_pos.x() + offset, start_pos.y())
        ctrl2 = QPointF(end_pos.x() - offset, end_pos.y())

        path.cubicTo(ctrl1, ctrl2, end_pos)

        self.setPath(path)
        label_pos = path.pointAtPercent(0.5)
        label_rect = self.condition_label.boundingRect()
        vertical_offset = -15
        self.condition_label.setPos(
            label_pos.x() - label_rect.width() / 2,
            label_pos.y() - label_rect.height() / 2 + vertical_offset
        )

    def destroy(self):
        if self.start_port and self in self.start_port.connections: self.start_port.connections.remove(self)
        if self.end_port and self in self.end_port.connections: self.end_port.connections.remove(self)
        self._scene.removeItem(self)

    def serialize(self):
        if not self.start_port or not self.end_port:
            return None
        return {
            'start_node_uuid': self.start_port.parentItem().uuid,
            'end_node_uuid': self.end_port.parentItem().uuid,
            'condition': self.condition,
        }

class DataSocket(QGraphicsObject):
    # Added a label to identify sockets (e.g., 'A', 'B', 'C')
    def __init__(self, parent, is_output=False, label=None):
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
        return QRectF(-self.radius - 2, -self.radius - 2, 2 * self.radius + 4, 2 * self.radius + 4)

    def paint(self, painter, option, widget=None):
        painter.setBrush(QBrush(QColor("#ffc400")))
        painter.setPen(QPen(Qt.GlobalColor.black, 1))
        painter.drawRect(-self.radius, -self.radius, 2 * self.radius, 2 * self.radius)

    def itemChange(self, change, value):
        if change == QGraphicsObject.GraphicsItemChange.ItemScenePositionHasChanged:
            for conn in self.connections:
                conn.update_path()
        return value

class DataConnection(QGraphicsPathItem):
    """A visual data connection with draggable horizontal and vertical segments."""
    def __init__(self, start_socket, end_socket, scene, uuid_str=None):
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

        # Control points for horizontal and vertical segments
        self.h_control_y1 = None
        self.h_control_y2 = None
        self.v_control_x = None
        
        self.drag_handle = None # Can be 'v_handle', 'h1_handle', or 'h2_handle'

        self.update_path()

    def shape(self):
        stroker = QPainterPathStroker()
        stroker.setWidth(10)
        return stroker.createStroke(self.path())

    def set_state(self, new_state):
        self.state = new_state
        self.update()

    def paint(self, painter, option, widget=None):
        color = "#f0e68c" if self.state == "active" else "#ffc400"
        pen = QPen(QColor(color), 2, Qt.PenStyle.DashLine)
        if self.isSelected():
            pen.setColor(QColor("#ffffff"))
            pen.setStyle(Qt.PenStyle.SolidLine)
        painter.setPen(pen)
        painter.drawPath(self.path())

        # Draw handles if selected
        if self.isSelected():
            painter.setBrush(QBrush(QColor("#00aaff")))
            painter.setPen(QPen(Qt.GlobalColor.white))
            
            handles = self.get_handle_positions()
            for handle_pos in handles.values():
                if handle_pos:
                    painter.drawRoundedRect(QRectF(handle_pos.x() - 4, handle_pos.y() - 4, 8, 8), 2, 2)
    
    def get_handle_positions(self):
        """Calculates the positions for the draggable handles."""
        start_pos = self.start_socket.scenePos()
        end_pos = self.end_socket.scenePos() if self.end_socket else self._scene.mouse_move_pos
        
        h1_handle_pos = QPointF((self.v_control_x + start_pos.x()) / 2, self.h_control_y1)
        v_handle_pos = QPointF(self.v_control_x, (self.h_control_y1 + self.h_control_y2)/2)
        h2_handle_pos = QPointF((self.v_control_x + end_pos.x()) / 2, self.h_control_y2)

        return {'h1': h1_handle_pos, 'v': v_handle_pos, 'h2': h2_handle_pos}

    def update_path(self):
        """Draws the path with distinct horizontal and vertical segments."""
        path = QPainterPath()
        start_pos = self.start_socket.scenePos()
        end_pos = self.end_socket.scenePos() if self.end_socket else self._scene.mouse_move_pos

        # Initialize control points if they don't exist
        if self.v_control_x is None:
            self.v_control_x = (start_pos.x() + end_pos.x()) / 2
        if self.h_control_y1 is None:
            self.h_control_y1 = start_pos.y() + 20
        if self.h_control_y2 is None:
             self.h_control_y2 = end_pos.y() - 20

        # Create a 5-segment path
        p1 = QPointF(start_pos.x(), self.h_control_y1)
        p2 = QPointF(self.v_control_x, self.h_control_y1)
        p3 = QPointF(self.v_control_x, self.h_control_y2)
        p4 = QPointF(end_pos.x(), self.h_control_y2)

        path.moveTo(start_pos)
        path.lineTo(p1)
        path.lineTo(p2)
        path.lineTo(p3)
        path.lineTo(p4)
        path.lineTo(end_pos)
        
        self.setPath(path)

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        self.drag_handle = None
        if self.isSelected():
            pos = event.pos()
            handles = self.get_handle_positions()
            
            # Check handles in order of appearance
            if (pos - handles['h1']).manhattanLength() < 10:
                self.drag_handle = 'h1_handle'
            elif (pos - handles['v']).manhattanLength() < 10:
                 self.drag_handle = 'v_handle'
            elif (pos - handles['h2']).manhattanLength() < 10:
                 self.drag_handle = 'h2_handle'

    def mouseMoveEvent(self, event):
        if self.drag_handle == 'h1_handle':
            self.h_control_y1 = event.pos().y()
            self.update_path()
        elif self.drag_handle == 'v_handle':
            self.v_control_x = event.pos().x()
            self.update_path()
        elif self.drag_handle == 'h2_handle':
            self.h_control_y2 = event.pos().y()
            self.update_path()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self.drag_handle = None
        super().mouseReleaseEvent(event)

    def destroy(self):
        if self.start_socket and self in self.start_socket.connections:
            self.start_socket.connections.remove(self)
        if self.end_socket and self in self.end_socket.connections:
            self.end_socket.connections.remove(self)
        self._scene.removeItem(self)

    def serialize(self):
        if not self.start_socket or not self.end_socket:
            return None
        return {
            'uuid': self.uuid,
            'start_node_uuid': self.start_socket.parentItem().uuid,
            'end_node_uuid': self.end_socket.parentItem().uuid,
            'h_control_y1': self.h_control_y1,
            'h_control_y2': self.h_control_y2,
            'v_control_x': self.v_control_x,
            'end_socket_label': self.end_socket.label if hasattr(self.end_socket, 'label') else None
        }

class MinimapView(QGraphicsView):
    def __init__(self, main_view, parent=None):
        super().__init__(parent)
        self.main_view = main_view
        self.setScene(self.main_view.scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setInteractive(False)
        self.visible_rect_item = QGraphicsRectItem()
        self.visible_rect_item.setPen(QPen(QColor(255, 255, 255, 150), 2))
        self.visible_rect_item.setBrush(QBrush(QColor(255, 255, 255, 50)))
        self.scene().addItem(self.visible_rect_item)
        self.main_view.viewport().installEventFilter(self)
        self.update_visible_rect()

    def eventFilter(self, source, event):
        if source == self.main_view.viewport() and event.type() == event.Type.Resize:
            self.update_visible_rect()
        return super().eventFilter(source, event)

    def update_visible_rect(self):
        self.fitInView(self.scene().sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
        visible_scene_rect = self.main_view.mapToScene(self.main_view.viewport().rect()).boundingRect()
        self.visible_rect_item.setRect(visible_scene_rect)

    def mousePressEvent(self, event):
        self.pan_to_position(event.pos())

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            self.pan_to_position(event.pos())

    def pan_to_position(self, pos):
        scene_pos = self.mapToScene(pos)
        self.main_view.centerOn(scene_pos)
        self.update_visible_rect()

class SequenceNode(QGraphicsObject):
    def __init__(self, config, uuid_str=None):
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
    
    def toggle_breakpoint(self):
        """Toggles the breakpoint state for this node."""
        self.has_breakpoint = not self.has_breakpoint
        self.config['has_breakpoint'] = self.has_breakpoint
        self.update() # Trigger a repaint

    def set_state(self, new_state):
        self.state = new_state
        self.update()

    def boundingRect(self): return QRectF(0, 0, self.width, self.height)

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget | None = ...):
        path = QPainterPath()
        path.addRoundedRect(self.boundingRect(), 10, 10)

        node_type = self.config.get('node_type')
        base_color = "#3c3f41"
        if node_type == NodeType.METHOD_CALL.value: base_color = "#2E4053"
        elif node_type == NodeType.DELAY.value: base_color = "#483D8B"
        elif node_type == NodeType.WRITE_VALUE.value: base_color = "#556B2F"
        elif node_type == NodeType.STATIC_VALUE.value: base_color = "#006464"
        elif node_type == NodeType.RUN_SEQUENCE.value: base_color = "#6A1B9A"
        elif node_type == NodeType.FOR_LOOP.value: base_color = "#8B4513"
        elif node_type == NodeType.WHILE_LOOP.value: base_color = "#1E8449"
        elif node_type == NodeType.COMPUTE.value: base_color = "#BF360C" # NEW COLOR

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
        title_text = self.config.get('label', 'Unknown')
        if self.config.get('has_argument'):
            title_text += " *"
        self.title.setPlainText(title_text)
        self.center_title()

    def serialize(self):
        return {
            'uuid': self.uuid,
            'config': self.config,
            'pos': {'x': self.pos().x(), 'y': self.pos().y()},
            'has_breakpoint': self.has_breakpoint
        }
        
    def mousePressEvent(self, event):
        """When a node is pressed, temporarily disable the view's rubber band drag mode."""
        if self.scene() and self.scene().views():
            self.scene().views()[0].setDragMode(QGraphicsView.DragMode.NoDrag)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        """When the node is released, restore the view's rubber band drag mode."""
        if self.scene() and self.scene().views():
            self.scene().views()[0].setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        super().mouseReleaseEvent(event)
        
    def highlight(self):
        """Animates the node to draw attention to it."""
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
                if item.control_point:
                    data['control_point'] = item.control_point
            
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
                        conn = DataConnection(start_node.data_out_socket, end_socket, self.scene)
                        if 'control_point' in data:
                            conn.control_point = data.get('control_point')
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
        if isinstance(item_at_pos, SequenceNode):
            toggle_breakpoint_action = menu.addAction("Toggle Breakpoint")
            action = menu.exec(event.screenPos())
            if action == toggle_breakpoint_action:
                item_at_pos.toggle_breakpoint()
                self.scene_changed.emit()
            return
            
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
                    
                    if self.temp_connection.start_port.parentItem().config.get('node_type') in [NodeType.FOR_LOOP.value, NodeType.WHILE_LOOP.value]:
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
            if node_type == NodeType.METHOD_CALL.value or node_type == NodeType.WRITE_VALUE.value:
                dialog = NodeConfigDialog(self.views()[0], current_config=item.config)
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
                    self.scene_changed.emit()
        super().mouseDoubleClickEvent(event)

class SequenceEditor(QGraphicsView):       
    scene_changed = pyqtSignal()    

    """The main view widget for the sequencer scene."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = SequenceScene(self)
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
        self.minimap = MinimapView(self, self)
        self.minimap.setFixedSize(200, 150)
        self.horizontalScrollBar().valueChanged.connect(self.minimap.update_visible_rect)
        self.verticalScrollBar().valueChanged.connect(self.minimap.update_visible_rect)
        
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

    def zoom_out(self):
        """Scales the view down by 20%."""
        self.scale(1 / 1.2, 1 / 1.2)

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

    def resizeEvent(self, event):
        """Ensure the find widget stays in the top-right corner."""
        super().resizeEvent(event)
        if self.find_widget:
            self.find_widget.move(self.width() - self.find_widget.width() - 10, 10)

        # Position minimap in bottom-right corner
        if self.minimap:
            self.minimap.move(self.width() - self.minimap.width() - 10, self.height() - self.minimap.height() - 10)

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
        for item in self.scene.items():
            if isinstance(item, (SequenceNode, CommentNode)):
                nodes.append(item.serialize())
            elif isinstance(item, Connection):
                serialized_conn = item.serialize()
                if serialized_conn:
                    exec_connections.append(serialized_conn)
            elif isinstance(item, DataConnection):
                serialized_conn = item.serialize()
                if serialized_conn:
                    data_connections.append(serialized_conn)
        return {'nodes': nodes, 'exec_connections': exec_connections, 'data_connections': data_connections}

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
                        if conn_data.get('control_point'):
                            cp = conn_data['control_point']
                            connection.control_point = QPointF(cp['x'], cp['y'])
                        connection.update_path()
                        self.scene.addItem(connection)