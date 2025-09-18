"""
A QTreeWidget for Browsing the OPC-UA Server's Node Structure.

This module provides the ServerTreeView, which lazily populates with nodes
from the connected OPC-UA server. It allows users to interact with nodes via a
context menu to add them to the dashboard or the sequencer.
"""
import logging
from asyncua import ua
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLineEdit, QTreeWidget, QTreeWidgetItem, QMenu, QApplication, QTreeWidgetItemIterator
from PyQt6.QtCore import Qt, pyqtSignal, QMimeData
from PyQt6.QtGui import QAction, QDrag

class ServerTreeView(QWidget):
    """
    A widget that contains a search bar and a QTreeWidget for browsing the OPC-UA server.
    """
    create_widget_requested = pyqtSignal(dict)
    add_to_sequencer_requested = pyqtSignal(dict)

    def __init__(self, opcua_logic, async_runner, parent=None):
        super().__init__(parent)
        self.opcua_logic = opcua_logic
        self.async_runner = async_runner
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search nodes...")
        self.search_bar.textChanged.connect(self.filter_tree)
        layout.addWidget(self.search_bar)
        
        self.tree_widget = QTreeWidget()
        self.tree_widget.setHeaderLabel("OPC-UA Server")
        self.tree_widget.itemExpanded.connect(self.on_item_expanded)
        self.tree_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree_widget.customContextMenuRequested.connect(self.open_context_menu)
        layout.addWidget(self.tree_widget)

        self.node_map = {}
        
        # REMOVED: All drag-and-drop related code has been removed for stability.

    # def populate_root(self):
    #     """Clears the tree and adds the root 'Objects' node."""
    #     self.clear()
    #     if self.opcua_logic.is_connected:
    #         root_node = self.opcua_logic.client.get_objects_node()
    #         root_item = QTreeWidgetItem(self, ["Objects"])
    #         root_item.addChild(QTreeWidgetItem(["Loading..."]))
    #         self.node_map[id(root_item)] = root_node
    
    def populate_root(self):
        """Clears the tree and adds top-level nodes (Objects, Types, Views, etc.) under Root."""
        self.tree_widget.clear()

        if self.opcua_logic.is_connected:
            root_node = self.opcua_logic.client.get_root_node()
            self.node_map.clear()

            root_item = QTreeWidgetItem(self.tree_widget, ["Root"])
            root_item.addChild(QTreeWidgetItem(["Loading..."]))
            self.node_map[id(root_item)] = root_node
            self.tree_widget.addTopLevelItem(root_item)

            # Trigger lazy loading for root's children immediately
            self.async_runner.submit(self.populate_children(root_item, root_node))

    def on_item_expanded(self, item):
        """Called when a user expands a tree item."""
        if item.childCount() > 0 and item.child(0).text(0) == "Loading...":
            node = self.node_map.get(id(item))
            if node and self.async_runner:
                self.async_runner.submit(self.populate_children(item, node))

    # async def populate_children(self, parent_item, parent_node):
    #     """Asynchronously fetches and adds the children of a given node to the tree."""
    #     try:
    #         children = await parent_node.get_children()
    #         parent_item.takeChildren()

    #         if not children:
    #             return

    #         for child_node in children:
    #             bname = await child_node.read_browse_name()
    #             child_item = QTreeWidgetItem(parent_item, [bname.Name])
                
    #             self.node_map[id(child_item)] = child_node
                
    #             node_class = await child_node.read_node_class()
    #             if node_class in [ua.NodeClass.Object, ua.NodeClass.View]:
    #                 child_item.addChild(QTreeWidgetItem(["Loading..."]))

    #     except Exception as e:
    #         logging.error(f"Failed to browse children for node {parent_node}: {e}")
    #         parent_item.takeChildren()
    #         parent_item.setText(0, f"{parent_item.text(0)} [Browse Error]")
    
    async def populate_children(self, parent_item, parent_node):
        try:
            # Default: hierarchical children
            children = await parent_node.get_children()

            # If no children found, try subtypes (for Types browsing)
            if not children:
                subtype_nodes = await parent_node.get_referenced_nodes(
                    refs=ua.ObjectIds.HasSubtype,
                    direction=ua.BrowseDirection.Forward
                )
                children = subtype_nodes

            parent_item.takeChildren()
            if not children:
                return

            for child_node in children:
                bname = await child_node.read_browse_name()
                child_item = QTreeWidgetItem(parent_item, [bname.Name])
                self.node_map[id(child_item)] = child_node

                node_class = await child_node.read_node_class()
                if node_class in [ua.NodeClass.Object, ua.NodeClass.ObjectType, ua.NodeClass.VariableType]:
                    child_item.addChild(QTreeWidgetItem(["Loading..."]))

        except Exception as e:
            logging.error(f"Failed to browse children for node {parent_node}: {e}")
            parent_item.takeChildren()
            parent_item.setText(0, f"{parent_item.text(0)} [Browse Error]")

    def open_context_menu(self, position):
        """
        Shows a context menu. The options shown depend on the node type,
        which is determined asynchronously.
        """
        item = self.tree_widget.itemAt(position)
        if not item: return

        node = self.node_map.get(id(item))
        if not node: return

        # Submit an async task to build and show the context menu
        self.async_runner.submit(self.build_and_show_context_menu(node, position))

    async def build_and_show_context_menu(self, node, position):
        """
        Asynchronously determines the node type and then creates and displays
        the appropriate context menu.
        """
        try:
            node_class = await node.read_node_class()
            
            context_menu = QMenu(self.tree_widget)
            
            # This menu is always available for Variables and Objects
            if node_class in [ua.NodeClass.Variable, ua.NodeClass.Object]:
                add_widget_menu = context_menu.addMenu("Add as Widget")
                display_num_action = QAction("Display (Numerical)", self.tree_widget)
                display_num_action.triggered.connect(lambda: self.request_widget_creation(node, "Numerical Display"))
                add_widget_menu.addAction(display_num_action)
                
                display_text_action = QAction("Display (Text)", self.tree_widget)
                display_text_action.triggered.connect(lambda: self.request_widget_creation(node, "Text Display"))
                add_widget_menu.addAction(display_text_action)
                
                input_str_action = QAction("Input (String)", self.tree_widget)
                input_str_action.triggered.connect(lambda: self.request_widget_creation(node, "String Input"))
                add_widget_menu.addAction(input_str_action)

                input_num_action = QAction("Input (Numerical)", self.tree_widget)
                input_num_action.triggered.connect(lambda: self.request_widget_creation(node, "Numerical Input"))
                add_widget_menu.addAction(input_num_action)
                
                switch_action = QAction("Switch (Boolean)", self.tree_widget)
                switch_action.triggered.connect(lambda: self.request_widget_creation(node, "Switch"))
                add_widget_menu.addAction(switch_action)

            # This option is specific to Method nodes
            if node_class == ua.NodeClass.Method:
                add_to_seq_action = QAction("Add to Sequencer", self.tree_widget)
                add_to_seq_action.triggered.connect(lambda: self.request_sequencer_add(node))
                context_menu.addAction(add_to_seq_action)

                context_menu.addSeparator()

                # Allow adding a method as a simple button widget as well
                button_action = QAction("Add as Button Widget", self.tree_widget)
                button_action.triggered.connect(lambda: self.request_widget_creation(node, "Button"))
                context_menu.addAction(button_action)

            # Only show the menu if there are any actions available
            if not context_menu.isEmpty():
                context_menu.exec(self.tree_widget.viewport().mapToGlobal(position))

        except Exception as e:
            logging.error(f"Could not build context menu: {e}")

    def request_widget_creation(self, node, widget_type):
        """Starts the process of creating a dashboard widget."""
        self.async_runner.submit(self.get_node_info_and_emit(node, widget_type))

    def request_sequencer_add(self, node):
        """Starts the process of adding a node to the sequencer."""
        self.async_runner.submit(self.get_method_info_and_emit_for_sequencer(node))

    async def get_method_info_and_emit_for_sequencer(self, node):
        """Gathers info for a method node and emits the sequencer signal."""
        try:
            # Double-check it's a method before emitting
            node_class = await node.read_node_class()
            if node_class != ua.NodeClass.Method:
                return

            parent = await node.get_parent()
            bname = await node.read_browse_name()
            
            config = {
                "label": bname.Name,
                "identifier": parent.nodeid.to_string(),
                "method_bname": bname.Name
            }
            self.add_to_sequencer_requested.emit(config)
            logging.info(f"Requested to add '{bname.Name}' to sequencer.")

        except Exception as e:
            logging.error(f"Could not get method info for sequencer: {e}")

    async def get_node_info_and_emit(self, node, widget_type):
        """Gets node info and emits a signal to the main window for widget creation."""
        try:
            bname = await node.read_browse_name()
            
            config = {
                "widget_type": widget_type,
                "label": bname.Name,
                "search_type": "By Node ID"
            }
            
            if widget_type == "Button":
                parent_node = await node.get_parent()
                config["identifier"] = parent_node.nodeid.to_string()
                config["method_bname"] = bname.Name
            else:
                config["identifier"] = node.nodeid.to_string()

            self.create_widget_requested.emit(config)
        except Exception as e:
            logging.error(f"Could not get node info for widget creation: {e}")

    def filter_tree(self, text):
        """Recursively filters the tree view based on the search text."""
        for i in range(self.tree_widget.topLevelItemCount()):
            self.filter_item(self.tree_widget.topLevelItem(i), text)

    def filter_item(self, item, text):
        """
        Recursively checks if an item or any of its children match the search text.
        Returns True if the item should be visible, False otherwise.
        """
        # An item is visible if its own text matches
        match = text.lower() in item.text(0).lower()

        # Or if any of its children should be visible
        child_match_found = False
        for i in range(item.childCount()):
            if self.filter_item(item.child(i), text):
                child_match_found = True
        
        is_visible = match or child_match_found
        item.setHidden(not is_visible)
        
        # Expand items that have visible children to show the matches
        if is_visible and child_match_found:
            item.setExpanded(True)
        
        return is_visible
