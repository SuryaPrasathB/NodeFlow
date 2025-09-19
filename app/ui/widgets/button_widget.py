import asyncio
from PyQt6.QtWidgets import QPushButton, QLineEdit, QLabel, QCheckBox, QVBoxLayout, QGraphicsOpacityEffect
from PyQt6.QtCore import QPropertyAnimation, QEasingCurve, QTimer, Qt
from .base_widget import BaseWidget

class ButtonWidget(BaseWidget):
    """
    A widget to call an OPC UA method with an optional argument.

    When maximized, it displays a button, a checkbox to enable an argument
    input field, and a label to show the result of the method call.
    When minimized, it becomes a single, compact button that provides
    temporary, animated feedback upon being clicked.
    """
    def __init__(self, config, opcua_logic, parent=None, async_runner=None):
        """
        Initializes the ButtonWidget.

        Args:
            config (dict): The configuration dictionary for the widget.
            opcua_logic (OpcuaClientLogic): The OPC UA logic instance.
            parent (QWidget, optional): The parent widget. Defaults to None.
            async_runner (AsyncRunner, optional): The runner for async tasks. Defaults to None.
        """
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
        minimized_layout = QVBoxLayout(self.minimized_widget)
        minimized_layout.setContentsMargins(8, 8, 8, 8) 
        self.minimized_button = QPushButton(button_text)
        self.minimized_button.setStyleSheet("font-size: 11pt;")
        minimized_layout.addWidget(self.minimized_button)
        
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
        """Finalizes widget setup after the OPC UA node is found."""
        self.status_label.setText(f"Ready to call method on {self.node.nodeid.to_string()}")

    def on_call_button_clicked(self):
        """
        Slot for the button's clicked signal.

        Submits the `call_method` coroutine to the async runner.
        """
        if self.node and self.async_runner:
            self.async_runner.submit(self.call_method())

    async def call_method(self):
        """
        Performs the asynchronous OPC UA method call.

        It retrieves the method name and argument (if any), calls the method,
        and then routes the result to the appropriate display method.
        """
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
                # Attempt to convert to float, otherwise use as string
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
        """
        Displays the result of the method call.

        Routes the result to the static label if maximized, or to the animated
        popup if minimized.

        Args:
            text (str): The HTML-formatted result string to display.
        """
        if self.is_minimized:
            self.show_animated_result(text)
        else:
            self.result_label.setText(text)
            self.result_clear_timer.start(4000)

    def clear_result_label(self):
        """Clears the result label in the maximized view after a delay."""
        self.result_label.setText("Result: N/A")

    def show_animated_result(self, text):
        """
        Creates and shows a temporary, animated popup label for feedback.

        The popup appears near the widget, fades in, stays for a few seconds,
        and then fades out.

        Args:
            text (str): The HTML-formatted result string to display.
        """
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
        """Safely deletes the animated popup widget and its animations."""
        if self.animated_popup:
            self.animated_popup.deleteLater()
            self.animated_popup = None
            self.popup_fade_out_anim = None
