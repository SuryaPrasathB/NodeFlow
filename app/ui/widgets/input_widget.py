from PyQt6.QtWidgets import QLineEdit, QHBoxLayout, QPushButton, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt
from .base_widget import BaseWidget
from asyncua import ua
import asyncio

class InputWidget(BaseWidget):
    def __init__(self, config, opcua_logic, parent=None, async_runner=None):
        super().__init__(config, opcua_logic, parent, async_runner)
        
        h_layout = QHBoxLayout()
        self.input_field = QLineEdit()
        self.write_button = QPushButton("Write")
        h_layout.addWidget(self.input_field)
        h_layout.addWidget(self.write_button)
        self.content_area_layout.addLayout(h_layout)
        self.write_button.clicked.connect(self.on_write_clicked)
        
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
        self.minimized_widget.setStyleSheet("#minimizedWidget { background-color: #3c3f41; border: 1px solid #555; border-radius: 4px; } QLabel { color: #f0f0f0; }")

    async def setup_widget(self):
        try:
            value = await self.opcua_logic.read_value(self.node)
            self.input_field.setText(str(value))
            self.minimized_value.setText(str(value))
            self.status_label.setText(f"Node: {self.node.nodeid.to_string()}")
        except Exception as e:
            self.set_error_state(f"Setup Error: {e}")

    def on_write_clicked(self):
        if self.async_runner: self.async_runner.submit(self.write_value())

    async def write_value(self):
        value_str = self.input_field.text()
        try:
            self.status_label.setText("Status: Writing...")
            datatype = ua.VariantType.String
            value = value_str
            if self.config['widget_type'] == 'Numerical Input':
                datatype = ua.VariantType.Double
                value = float(value_str)
            await self.opcua_logic.write_value(self.node, value, datatype)
            self.minimized_value.setText(str(value))
            self.status_label.setText(f"Node: {self.node.nodeid.to_string()}")
        except ValueError:
            self.status_label.setText(f"<font color='red'>Invalid number format</font>")
        except Exception as e:
            self.status_label.setText(f"<font color='red'>Write Error: {e}</font>")
