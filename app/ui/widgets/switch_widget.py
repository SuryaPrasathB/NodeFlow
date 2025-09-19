from PyQt6.QtWidgets import QCheckBox, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt
from .base_widget import BaseWidget
from asyncua import ua
import asyncio
import logging

class SwitchWidget(BaseWidget):
    """
    A widget with a toggle switch synchronized with an OPC UA boolean node.

    This widget uses a subscription to monitor a node's boolean value and
    reflects its state with a QCheckBox. Clicking the checkbox writes the new
    state back to the node. An internal flag prevents feedback loops between
    user actions and subscription updates.
    """
    def __init__(self, config, opcua_logic, parent=None, async_runner=None):
        """
        Initializes the SwitchWidget.

        Args:
            config (dict): The configuration dictionary for the widget.
            opcua_logic (OpcuaClientLogic): The OPC UA logic instance.
            parent (QWidget, optional): The parent widget. Defaults to None.
            async_runner (AsyncRunner, optional): The runner for async tasks. Defaults to None.
        """
        super().__init__(config, opcua_logic, parent, async_runner)
        
        # --- Standard View ---
        self.switch = QCheckBox("State")
        self.content_area_layout.addWidget(self.switch)
        self.switch.toggled.connect(self.on_switch_toggled)
        # Flag to prevent feedback loop between toggled signal and data changed signal
        self.is_internal_change = False

        # --- Minimized View ---
        minimized_layout = QVBoxLayout(self.minimized_widget)
        minimized_layout.setContentsMargins(5, 5, 5, 5)
        self.minimized_title = QLabel(f"<b>{config.get('label', 'N/A')}</b>")
        self.minimized_value = QLabel("---")
        minimized_font = self.minimized_value.font()
        minimized_font.setPointSize(14)
        self.minimized_value.setFont(minimized_font)
        self.minimized_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        minimized_layout.addWidget(self.minimized_title)
        minimized_layout.addWidget(self.minimized_value)
        
        self.minimized_widget.setStyleSheet("""
            #minimizedWidget {
                background-color: #3c3f41;
                border: 1px solid #555;
                border-radius: 4px;
            }
            QLabel { color: #f0f0f0; }
        """)

        self.subscription_handle = None

    async def setup_widget(self):
        """Reads the initial value and subscribes to future changes."""
        try:
            initial_value = await self.opcua_logic.read_value(self.node)
            self.on_data_changed(initial_value) # Use callback to set initial state
            self.status_label.setText(f"Node: {self.node.nodeid.to_string()}")

            self.subscription_handle = await self.opcua_logic.subscribe_to_node_change(self.node, self.on_data_changed)

        except Exception as e:
            self.set_error_state(f"Setup Error: {e}")

    def on_switch_toggled(self, checked):
        """
        Slot for the switch's toggled signal.

        Triggers an async write operation when the user toggles the switch.
        It ignores changes that are triggered internally by the subscription callback.

        Args:
            checked (bool): The new state of the switch.
        """
        if self.is_internal_change:
            return # Prevent feedback loop
        if self.async_runner:
            self.async_runner.submit(self.write_value(checked))

    def on_data_changed(self, value):
        """
        Callback for the OPC UA subscription. Updates the UI to reflect the server state.

        Args:
            value: The new value received from the subscription.
        """
        is_checked = bool(value)
        
        # Use a flag to prevent the toggled signal from firing when we update the UI
        self.is_internal_change = True
        self.switch.setChecked(is_checked)
        self.is_internal_change = False
        
        # Update the minimized view as well
        if is_checked:
            self.minimized_value.setText("<font color='#55ff7f'>ON</font>")
        else:
            self.minimized_value.setText("<font color='#ff5555'>OFF</font>")

    async def write_value(self, value):
        """
        Writes the new boolean value to the OPC UA server.

        Args:
            value (bool): The new state to write.
        """
        try:
            self.status_label.setText("Status: Writing...")
            await self.opcua_logic.write_value(self.node, value, ua.VariantType.Boolean)
            # No need to update UI state here, the subscription's on_data_changed will handle it
            self.status_label.setText(f"Node: {self.node.nodeid.to_string()}")
        except Exception as e:
            self.status_label.setText(f"<font color='red'>Write Error: {e}</font>")
            # Revert switch state on error by re-reading from server
            if self.async_runner:
                self.async_runner.submit(self.revert_state_on_error())
    
    async def revert_state_on_error(self):
        """
        Reads the current value from the server to revert the UI state after a write error.
        """
        try:
            current_val = await self.opcua_logic.read_value(self.node)
            self.on_data_changed(current_val)
        except Exception as e:
            logging.error(f"Failed to revert state after write error: {e}")

    def stop_subscription(self):
        """
        Stops the OPC UA subscription for this widget.

        This is called before the widget is deleted to ensure proper cleanup.
        """
        if self.subscription_handle and self.async_runner:
            self.async_runner.submit(
                self.opcua_logic.unsubscribe_from_node_change(self.node, self.subscription_handle)
            )
            self.subscription_handle = None
