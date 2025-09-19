from PyQt6.QtWidgets import QLabel, QVBoxLayout
from PyQt6.QtCore import Qt
from .base_widget import BaseWidget

class DisplayWidget(BaseWidget):
    """
    A widget to display a node's value using an efficient OPC-UA subscription.

    This widget shows the real-time value of an OPC UA node. It performs an
    initial read and then subscribes to the node for any subsequent changes,
    ensuring the displayed value is always up-to-date with minimal network traffic.
    """
    def __init__(self, config, opcua_logic, parent=None, async_runner=None):
        """
        Initializes the DisplayWidget.

        Args:
            config (dict): The configuration dictionary for the widget.
            opcua_logic (OpcuaClientLogic): The OPC UA logic instance.
            parent (QWidget, optional): The parent widget. Defaults to None.
            async_runner (AsyncRunner, optional): The runner for async tasks. Defaults to None.
        """
        super().__init__(config, opcua_logic, parent, async_runner)
        
        # --- Standard View ---
        self.display_label = QLabel("Value: N/A")
        font = self.display_label.font()
        font.setPointSize(14)
        self.display_label.setFont(font)
        self.content_area_layout.addWidget(self.display_label)
        
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
        
        # This will store the handle to the subscription so we can unsubscribe later.
        self.subscription_handle = None

    async def setup_widget(self):
        """
        Performs an initial read and then subscribes to future changes.
        """
        # Perform an initial read to populate the value immediately
        initial_value = await self.opcua_logic.read_value(self.node)
        self.on_data_changed(initial_value) # Use the callback to set the UI
        
        if self.node:
             self.status_label.setText(f"Node: {self.node.nodeid.to_string()}")
        
        # Subscribe to the node, passing our on_data_changed method as the callback.
        self.subscription_handle = await self.opcua_logic.subscribe_to_node_change(self.node, self.on_data_changed)

    def on_data_changed(self, value):
        """
        Callback method triggered by the OPC UA subscription on data change.

        It updates the UI with the new value, formatting it if necessary.

        Args:
            value: The new value received from the subscription.
        """
        try:
            display_value = ""
            if self.config["widget_type"] == "Numerical Display":
                try:
                    display_value = f"{float(value):.2f}"
                except (ValueError, TypeError):
                    display_value = str(value)
            else:
                display_value = str(value)
            
            # Update both views
            self.display_label.setText(f"Value: {display_value}")
            self.minimized_value.setText(display_value)

        except Exception as e:
            self.status_label.setText(f"<font color='orange'>Update Error</font>")
            self.minimized_value.setText("ERR")

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