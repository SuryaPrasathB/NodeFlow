from PyQt6.QtWidgets import QCheckBox, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt
from .base_widget import BaseWidget
from asyncua import ua
import asyncio
import logging

class SwitchWidget(BaseWidget):
    """
    A widget with a toggle switch that stays in sync using an OPC-UA subscription.
    """
    def __init__(self, config, opcua_logic, parent=None, async_runner=None):
        super().__init__(config, opcua_logic, parent, async_runner)
        
        # --- Standard View ---
        self.switch = QCheckBox("State")
        self.content_area_layout.addWidget(self.switch)
        self.switch.toggled.connect(self.on_switch_toggled)
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

        ## SUBSCRIPTION UPDATE ##
        self.subscription_handle = None

    async def setup_widget(self):
        """Reads the initial value and subscribes to future changes."""
        try:
            initial_value = await self.opcua_logic.read_value(self.node)
            self.on_data_changed(initial_value) # Use callback to set initial state
            self.status_label.setText(f"Node: {self.node.nodeid.to_string()}")

            ## SUBSCRIPTION UPDATE ##
            self.subscription_handle = await self.opcua_logic.subscribe_to_node_change(self.node, self.on_data_changed)

        except Exception as e:
            self.set_error_state(f"Setup Error: {e}")

    def on_switch_toggled(self, checked):
        """Triggers an async write operation when the user toggles the switch."""
        if self.is_internal_change:
            return # Prevent feedback loop
        if self.async_runner:
            self.async_runner.submit(self.write_value(checked))

    ## SUBSCRIPTION UPDATE ##
    def on_data_changed(self, value):
        """Callback for subscription. Updates the UI to reflect the server state."""
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
        """Writes the new boolean value to the OPC-UA server."""
        try:
            self.status_label.setText("Status: Writing...")
            await self.opcua_logic.write_value(self.node, value, ua.VariantType.Boolean)
            # No need to update state here, the subscription data change will handle it
            self.status_label.setText(f"Node: {self.node.nodeid.to_string()}")
        except Exception as e:
            self.status_label.setText(f"<font color='red'>Write Error: {e}</font>")
            # Revert switch state on error by re-reading from server
            # The subscription will eventually correct this, but a manual read is faster.
            if self.async_runner:
                self.async_runner.submit(self.revert_state_on_error())
    
    async def revert_state_on_error(self):
        try:
            current_val = await self.opcua_logic.read_value(self.node)
            self.on_data_changed(current_val)
        except Exception as e:
            logging.error(f"Failed to revert state after write error: {e}")

    ## SUBSCRIPTION UPDATE ##
    def stop_subscription(self):
        """Stops the subscription for this widget."""
        if self.subscription_handle and self.async_runner:
            self.async_runner.submit(
                self.opcua_logic.unsubscribe_from_node_change(self.node, self.subscription_handle)
            )
            self.subscription_handle = None
