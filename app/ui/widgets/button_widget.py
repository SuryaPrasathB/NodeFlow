import asyncio
from PyQt6.QtWidgets import QPushButton, QLineEdit, QLabel, QCheckBox, QVBoxLayout, QGraphicsOpacityEffect
from PyQt6.QtCore import QPropertyAnimation, QEasingCurve, QTimer, Qt
from .base_widget import BaseWidget

class ButtonWidget(BaseWidget):
    """
    A widget to call an OPC-UA method. When minimized, it becomes a single
    button that shows temporary, animated feedback on click.
    """
    def __init__(self, config, opcua_logic, parent=None, async_runner=None):
        super().__init__(config, opcua_logic, parent, async_runner)
        
        # --- Standard (Maximized) View ---
        button_text = config.get("method_bname", config.get('label', 'Call Method'))
        self.call_button = QPushButton(button_text)
        font = self.call_button.font()
        font.setPointSize(12)
        self.call_button.setFont(font)
        
        self.has_argument_checkbox = QCheckBox("Has Input Argument?")
        self.argument_input = QLineEdit()
        self.result_label = QLabel("Result: N/A")
        self.result_label.setWordWrap(True)

        self.content_area_layout.addWidget(self.call_button)
        self.content_area_layout.addWidget(self.has_argument_checkbox)
        self.content_area_layout.addWidget(self.argument_input)
        self.content_area_layout.addWidget(self.result_label)
        
        self.call_button.clicked.connect(self.on_call_button_clicked)
        self.has_argument_checkbox.toggled.connect(self.argument_input.setVisible)
        
        has_arg = config.get("has_argument", False)
        self.has_argument_checkbox.setChecked(has_arg)
        self.argument_input.setVisible(has_arg)
        self.argument_input.setPlaceholderText("Enter argument value")

        # --- Minimized View ---
        # FIX: Use a layout with margins to create a draggable border
        minimized_layout = QVBoxLayout(self.minimized_widget)
        # The margin creates the border area that can be used for dragging
        minimized_layout.setContentsMargins(8, 8, 8, 8) 
        self.minimized_button = QPushButton(button_text)
        self.minimized_button.setStyleSheet("font-size: 11pt;")
        minimized_layout.addWidget(self.minimized_button)
        
        # FIX: Style the container to make the border visible
        self.minimized_widget.setStyleSheet("""
            #minimizedWidget {
                background-color: #3c3f41;
                border: 1px solid #555;
                border-radius: 4px;
            }
        """)

        self.minimized_button.clicked.connect(self.on_call_button_clicked)
        
        # --- Animation and Timer Management ---
        self.result_clear_timer = QTimer(self)
        self.result_clear_timer.setSingleShot(True)
        self.result_clear_timer.timeout.connect(self.clear_result_label)
        
        self.animated_popup = None
        self.popup_fade_out_anim = None

    async def setup_widget(self):
        self.status_label.setText(f"Ready to call method on {self.node.nodeid.to_string()}")

    def on_call_button_clicked(self):
        if self.node and self.async_runner:
            self.async_runner.submit(self.call_method())

    async def call_method(self):
        if not self.is_minimized:
            self.result_label.setText("Result: Calling...")
        
        method_bname = self.config.get("method_bname")
        if not method_bname:
            self.show_result("<font color='red'>Error: Method name not configured.</font>")
            return
            
        args = []
        if self.has_argument_checkbox.isChecked():
            arg_text = self.argument_input.text()
            try:
                arg_value = float(arg_text)
            except ValueError:
                arg_value = arg_text
            args.append(arg_value)

        try:
            method_node = await self.opcua_logic.get_method_node(self.node, method_bname)
            if method_node is None:
                self.show_result(f"<font color='red'>Error: Method '{method_bname}' not found.</font>")
                return

            result = await self.node.call_method(method_node, *args)
            self.show_result(f"<b>Result:</b> {result}")
        except Exception as e:
            self.show_result(f"<font color='red'><b>Call Error:</b><br>{e}</font>")
    
    def show_result(self, text):
        if self.is_minimized:
            self.show_animated_result(text)
        else:
            self.result_label.setText(text)
            self.result_clear_timer.start(4000)

    def clear_result_label(self):
        self.result_label.setText("Result: N/A")

    def show_animated_result(self, text):
        if self.animated_popup:
            self.clear_animated_popup()

        self.animated_popup = QLabel(text, self.parent())
        self.animated_popup.setWordWrap(True)
        self.animated_popup.setStyleSheet("""
            background-color: #1e1f22; 
            color: white; 
            border: 1px solid #555; 
            border-radius: 4px; 
            padding: 8px;
        """)
        
        pos = self.pos()
        self.animated_popup.move(pos.x(), pos.y() + self.height() + 5)
        self.animated_popup.adjustSize()
        self.animated_popup.show()
        
        effect = QGraphicsOpacityEffect(self.animated_popup)
        self.animated_popup.setGraphicsEffect(effect)
        
        fade_in = QPropertyAnimation(effect, b"opacity")
        fade_in.setDuration(300)
        fade_in.setStartValue(0.0)
        fade_in.setEndValue(1.0)
        
        self.popup_fade_out_anim = QPropertyAnimation(effect, b"opacity")
        self.popup_fade_out_anim.setDuration(500)
        self.popup_fade_out_anim.setStartValue(1.0)
        self.popup_fade_out_anim.setEndValue(0.0)
        self.popup_fade_out_anim.finished.connect(self.clear_animated_popup)
        
        QTimer.singleShot(3000, lambda: self.popup_fade_out_anim.start())
        
        fade_in.start()
        self.animated_popup.fade_in = fade_in
    
    def clear_animated_popup(self):
        if self.animated_popup:
            self.animated_popup.deleteLater()
            self.animated_popup = None
            self.popup_fade_out_anim = None
