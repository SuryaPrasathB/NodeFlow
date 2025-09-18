import pyqtgraph as pg
from PyQt6.QtWidgets import QVBoxLayout
from app.ui.widgets.base_widget import BaseWidget
from collections import deque
import numpy as np

class PlotterWidget(BaseWidget):
    def __init__(self, config, opcua_logic, parent=None, async_runner=None):
        super().__init__(config, opcua_logic, parent, async_runner)
        self.plot_widget = pg.PlotWidget()
        self.content_area_layout.addWidget(self.plot_widget)

        self.data_buffer = deque(maxlen=config.get('buffer_size', 100))
        self.plot_curve = self.plot_widget.plot(pen='y')

    async def setup_widget(self):
        self.status_label.setText("Status: Subscribing...")
        try:
            self.subscription = await self.opcua_logic.subscribe_to_node(self.node, self.on_data_change)
            self.status_label.setText("Status: OK")
        except Exception as e:
            self.set_error_state(f"Sub Error: {e}")

    def on_data_change(self, node, val, data):
        self.data_buffer.append(float(val))
        self.plot_curve.setData(np.array(self.data_buffer))

    def stop_subscription(self):
        if hasattr(self, 'subscription'):
            self.async_runner.submit(self.opcua_logic.unsubscribe_from_node(self.subscription))

    def serialize(self):
        # Add plotter-specific config to serialization
        base_data = super().serialize()
        base_data['config']['buffer_size'] = self.data_buffer.maxlen
        return base_data
