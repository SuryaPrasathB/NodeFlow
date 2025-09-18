from PyQt6.QtWidgets import QFrame, QVBoxLayout, QGridLayout, QLabel, QWidget, QMenu, QApplication, QPushButton, QLineEdit
from PyQt6.QtCore import pyqtSignal, Qt, QEvent, QSize
from PyQt6.QtGui import QCursor, QAction, QMouseEvent

class BaseWidget(QFrame):
    """
    Base class for dashboard widgets. Now includes robust drag-and-drop for
    minimized widgets that are also clickable.
    """
    request_delete = pyqtSignal(QWidget)
    request_copy = pyqtSignal(dict)
    request_duplicate = pyqtSignal(dict)
    state_changed = pyqtSignal(bool)
    
    def __init__(self, config, opcua_logic, parent=None, async_runner=None):
        super().__init__(parent)
        self.config = config
        self.opcua_logic = opcua_logic
        self.async_runner = async_runner
        self.node = None
        
        self.is_deletable = False
        self.drag_position = None
        self.is_resizing = False
        self.is_minimized = False
        self._original_size = QSize()
        self._minimized_size = None
        self._selected = False
        
        self.drag_start_pos = None
        self.is_potential_drag = False
        
        self.setObjectName("baseWidgetFrame")
        self.setMouseTracking(True)

        # --- Create all widget attributes first to prevent race conditions ---
        self.content_widget = QWidget()
        self.minimized_widget = QWidget()
        self.delete_overlay = QWidget(self)

        # --- Now, configure and lay out the widgets ---
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setFrameShadow(QFrame.Shadow.Plain)

        self.frame_layout = QGridLayout(self)
        self.frame_layout.setContentsMargins(0, 0, 0, 0)

        # Add stylesheet for BaseWidget selection border
        self.setStyleSheet("""
            #baseWidgetFrame {
                border: 2px solid transparent;
                border-radius: 4px;
            }
            #baseWidgetFrame[selected="true"] {
                border-color: #5a98d1;
            }
        """)

        # Configure content_widget
        self.content_widget.setObjectName("contentWidget")
        self.content_widget.setMouseTracking(True)
        self.content_widget.setStyleSheet("""
            #contentWidget {
                background-color: #3c3f41;
                border-radius: 4px;
            }
            QLabel { color: #f0f0f0; background-color: transparent; }
        """)
        self.frame_layout.addWidget(self.content_widget, 0, 0)

        # Configure main layout within the content_widget
        self.main_layout = QVBoxLayout(self.content_widget)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.main_layout.setSpacing(6)
        self.title_label = QLabel(f"<b>{config.get('label', 'N/A')}</b>")
        self.title_label.setMouseTracking(True)
        self.main_layout.addWidget(self.title_label)
        self.content_area_layout = QVBoxLayout()
        self.main_layout.addLayout(self.content_area_layout)
        self.main_layout.addStretch(1)
        self.status_label = QLabel("Status: Initializing...")
        self.status_label.setStyleSheet("font-size: 9pt; color: gray;")
        self.status_label.setMouseTracking(True)
        self.main_layout.addWidget(self.status_label)

        # Configure minimized_widget
        self.minimized_widget.setObjectName("minimizedWidget")
        self.minimized_widget.setMouseTracking(True)
        self.minimized_widget.hide()
        self.minimized_widget.installEventFilter(self)
        self.frame_layout.addWidget(self.minimized_widget, 0, 0)
        
        # Configure delete_overlay
        self.delete_overlay.setStyleSheet("background-color: rgba(255, 0, 0, 0.4); border-radius: 4px;")
        self.delete_overlay.hide()
        self.delete_overlay.installEventFilter(self)
        
        self.resize(320, 180)
        self.setMinimumSize(160, 80)
        
        def propagate_mouse_press(widget, parent):
            widget.installEventFilter(parent)
            for child in widget.findChildren(QWidget):
                # Don't install filter on interactive children like buttons or inputs
                if not isinstance(child, (QPushButton, QLineEdit)):
                    propagate_mouse_press(child, parent)

        propagate_mouse_press(self, self)
    
    def isSelected(self):
        """Returns whether the widget is selected."""
        return self._selected

    def setSelected(self, selected: bool):
        """Sets the selection state and updates the style property."""
        self._selected = selected
        self.setProperty("selected", selected)
        # Re-polish the widget to apply the new style state
        self.style().unpolish(self)
        self.style().polish(self)

    def clear_all_selections_in_parent(self):
        """Utility to clear selection from all sibling widgets in the same parent container."""
        parent = self.parent()
        if parent:
            for widget in parent.findChildren(BaseWidget):
                widget.setSelected(False)
        
    def serialize(self):
        """Serializes the widget's state for copy/paste or saving."""
        pos = self.pos()
        size = self.size()

        if self.is_minimized:
            # When minimized, 'geometry' holds the restored size, and 'minimized_size' holds the current size.
            geometry = {
                "x": pos.x(), "y": pos.y(),
                "width": self._original_size.width(), "height": self._original_size.height()
            }
            minimized_size = {"width": size.width(), "height": size.height()}
        else:
            # When not minimized, 'geometry' is the current size.
            geometry = {
                "x": pos.x(), "y": pos.y(),
                "width": size.width(), "height": size.height()
            }
            minimized_size = None

        return {
            "config": self.config,
            "geometry": geometry,
            "is_minimized": self.is_minimized,
            "original_size": {"width": self._original_size.width(), "height": self._original_size.height()} if self._original_size.isValid() else None,
            "minimized_size": minimized_size
        }

    async def initialize(self):
        # SequenceWidget does not have an identifier, handle this case
        if 'identifier' not in self.config:
            await self.setup_widget()
            return
            
        try:
            self.node = await self.opcua_logic.find_node(
                self.config['identifier'], self.config['search_type']
            )
            if self.node:
                await self.setup_widget()
            else:
                self.set_error_state("Node not found.")
        except Exception as e:
            self.set_error_state(f"Init Error: {e}")

    async def setup_widget(self):
        raise NotImplementedError("Subclasses must implement this method.")

    def stop_subscription(self):
        """
        Virtual method to be overridden by subclasses that use subscriptions.
        This ensures that when a widget is deleted, its subscription is properly terminated.
        """
        pass

    def set_error_state(self, message):
        self.status_label.setText(f"<font color='red'>{message}</font>")
        self.setEnabled(False)

    def set_delete_mode(self, deletable):
        self.is_deletable = deletable
        if deletable:
            self.delete_overlay.resize(self.size())
            self.delete_overlay.show()
            self.delete_overlay.raise_()
        else:
            self.delete_overlay.hide()
            
    def _handle_press_for_selection_and_drag(self, event):
        """Unified handler for mouse presses for selection and dragging."""
        self.raise_()
        is_ctrl_pressed = QApplication.keyboardModifiers() & Qt.KeyboardModifier.ControlModifier

        # --- Selection Logic ---
        if is_ctrl_pressed:
            self.setSelected(not self.isSelected())
        else:
            # If we click on a widget that is not already selected, clear others.
            if not self.isSelected():
                self.clear_all_selections_in_parent()
                self.setSelected(True)
        
        # --- Drag/Resize Initiation ---
        if self.isSelected():
            # Use global position to calculate local position in BaseWidget
            local_pos = self.mapFromGlobal(event.globalPosition().toPoint())
            resize_margin = 10
            at_resize_handle = (local_pos.x() > self.width() - resize_margin and
                                local_pos.y() > self.height() - resize_margin)

            if at_resize_handle:
                self.is_resizing = True
            # Only allow dragging if the widget is not minimized
            elif not self.is_minimized:
                self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def eventFilter(self, source, event):
        # This filter is installed on children by propagate_mouse_press.
        # It handles selection and drag initiation for clicks anywhere inside the widget.
        if (source is not self and source is not self.delete_overlay and source is not self.minimized_widget and
                event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton):
            self._handle_press_for_selection_and_drag(event)
            return True # Event handled, don't propagate further

        # Original logic for delete overlay
        if source is self.delete_overlay and event.type() == QEvent.Type.MouseButtonPress:
            if self.is_deletable:
                self.request_delete.emit(self)
                return True

        # Original logic for minimized widget dragging
        if source is self.minimized_widget:
            if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                self.raise_()
                return True 
            elif event.type() == QEvent.Type.MouseMove:
                if self.drag_position is not None:
                    self.move(event.globalPosition().toPoint() - self.drag_position)
                return True
            elif event.type() == QEvent.Type.MouseButtonRelease and event.button() == Qt.MouseButton.LeftButton:
                if self.drag_position:
                    grid_size = self.parent().grid_size if hasattr(self.parent(), 'grid_size') else 20
                    pos = self.pos()
                    new_x = round(pos.x() / grid_size) * grid_size
                    new_y = round(pos.y() / grid_size) * grid_size
                    self.move(new_x, new_y)
                self.drag_position = None
                return True
        
        return super().eventFilter(source, event)
        
    def contextMenuEvent(self, event):
        context_menu = QMenu(self)
        if self.is_minimized:
            maximize_action = QAction("Maximize", self)
            maximize_action.triggered.connect(self.toggle_minimize_state)
            context_menu.addAction(maximize_action)
        else:
            minimize_action = QAction("Minimize", self)
            minimize_action.triggered.connect(self.toggle_minimize_state)
            context_menu.addAction(minimize_action)

        context_menu.addSeparator()

        front_action = QAction("Bring to Front", self)
        front_action.triggered.connect(self.bring_to_front)
        context_menu.addAction(front_action)

        back_action = QAction("Send to Back", self)
        back_action.triggered.connect(self.send_to_back)
        context_menu.addAction(back_action)

        context_menu.addSeparator()
        copy_action = QAction("Copy", self)
        copy_action.triggered.connect(lambda: self.request_copy.emit(self.config))
        context_menu.addAction(copy_action)
        duplicate_action = QAction("Duplicate", self)
        duplicate_action.triggered.connect(lambda: self.request_duplicate.emit(self.config))
        context_menu.addAction(duplicate_action)
        context_menu.addSeparator()
        delete_action = QAction("Delete", self)
        delete_action.triggered.connect(lambda: self.request_delete.emit(self))
        context_menu.addAction(delete_action)
        context_menu.exec(event.globalPos())

    def bring_to_front(self):
        self.raise_()
        self.state_changed.emit(self.is_minimized)

    def send_to_back(self):
        self.lower()
        self.state_changed.emit(self.is_minimized)

    def toggle_minimize_state(self):
        self.is_minimized = not self.is_minimized
        
        if self.is_minimized:
            # If the widget is being minimized for the first time, or original size is not set, store current size.
            if not self._original_size.isValid():
                self._original_size = self.size()
            
            self.content_widget.hide()
            self.minimized_widget.show()

            # Resize to last known minimized size, or default.
            if self._minimized_size:
                self.resize(self._minimized_size)
            else:
                self.resize(160, 60)

            self.setMaximumSize(16777215, 16777215) # Allow resizing
            self.setMinimumSize(80, 40) # Set a reasonable minimum for minimized
        else:
            # Restore to original size
            self.minimized_widget.hide()
            self.content_widget.show()
            self.resize(self._original_size)
            self.setMinimumSize(160, 80)
            self.setMaximumSize(16777215, 16777215)
        
        self.state_changed.emit(self.is_minimized)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'delete_overlay') and self.delete_overlay:
            self.delete_overlay.resize(event.size())

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._handle_press_for_selection_and_drag(event)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.drag_position is not None or self.is_resizing:
            if hasattr(self.parent(), 'set_dragged_widget'):
                self.parent().set_dragged_widget(self)

        if self.drag_position is not None:
            self.move(event.globalPosition().toPoint() - self.drag_position)
        
        if self.is_resizing:
            self.resize(event.pos().x(), event.pos().y())
        else:
            resize_margin = 10
            if (event.pos().x() > self.width() - resize_margin and
                event.pos().y() > self.height() - resize_margin):
                self.setCursor(QCursor(Qt.CursorShape.SizeFDiagCursor))
            else:
                self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
            
    def mouseReleaseEvent(self, event):
        if hasattr(self.parent(), 'set_dragged_widget'):
            self.parent().set_dragged_widget(None)

        grid_size = self.parent().grid_size if hasattr(self.parent(), 'grid_size') else 20
        if self.is_resizing:
            new_width = round(self.width() / grid_size) * grid_size
            new_height = round(self.height() / grid_size) * grid_size
            self.resize(new_width, new_height)
            
            # If minimized, save this new size as the preferred minimized size.
            if self.is_minimized:
                self._minimized_size = self.size()

        if self.drag_position:
            pos = self.pos()
            new_x = round(pos.x() / grid_size) * grid_size
            new_y = round(pos.y() / grid_size) * grid_size
            self.move(new_x, new_y)

        self.drag_position = None
        self.is_resizing = False
        self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
