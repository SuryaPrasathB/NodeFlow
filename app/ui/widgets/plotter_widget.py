import pyqtgraph as pg
from PyQt6.QtWidgets import QVBoxLayout
from app.ui.widgets.base_widget import BaseWidget
from collections import deque
import numpy as np

class PlotterWidget(BaseWidget):
    """
    A widget for plotting real-time data from an OPC UA node.

    It uses `pyqtgraph` to display a line chart that updates with new values
    received from an OPC UA subscription. A deque is used as a circular buffer
    to store a moving window of the most recent data points.
    """
    def __init__(self, config, opcua_logic, parent=None, async_runner=None):
        """
        Initializes the PlotterWidget.

        Args:
            config (dict): The configuration dictionary for the widget.
            opcua_logic (OpcuaClientLogic): The OPC UA logic instance.
            parent (QWidget, optional): The parent widget. Defaults to None.
            async_runner (AsyncRunner, optional): The runner for async tasks. Defaults to None.
        """
        super().__init__(config, opcua_logic, parent, async_runner)
        self.plot_widget = pg.PlotWidget()
        self.content_area_layout.addWidget(self.plot_widget)

        buffer_size = config.get('buffer_size', 100)
        self.data_buffer = deque(maxlen=buffer_size)
        self.plot_curve = self.plot_widget.plot(pen='y')

    async def setup_widget(self):
        """
        Subscribes to the OPC UA node to start receiving data for plotting.
        """
        self.status_label.setText("Status: Subscribing...")
        try:
            self.subscription_handle = await self.opcua_logic.subscribe_to_node_change(self.node, self.on_data_change)
            self.status_label.setText("Status: OK")
        except Exception as e:
            self.set_error_state(f"Sub Error: {e}")

    def on_data_change(self, value):
        """
        Callback method for the OPC UA subscription.

        This is called every time the subscribed node's value changes. It adds
        the new value to the data buffer and updates the plot.

        Args:
            value: The new value received from the subscription.
        """
        try:
            self.data_buffer.append(float(value))
            self.plot_curve.setData(np.array(self.data_buffer))
        except (ValueError, TypeError):
            # Ignore non-numeric values
            pass

    def stop_subscription(self):
        """
        Stops the OPC UA subscription for this widget.

        This is called before the widget is deleted to ensure proper cleanup.
        """
        if hasattr(self, 'subscription_handle') and self.subscription_handle:
            self.async_runner.submit(self.opcua_logic.unsubscribe_from_node_change(self.node, self.subscription_handle))
            self.subscription_handle = None

    def serialize(self):
        """
        Serializes the widget's state, including plotter-specific config.

        Returns:
            dict: A dictionary containing the widget's state.
        """
        base_data = super().serialize()
        base_data['config']['buffer_size'] = self.data_buffer.maxlen
        return base_data
