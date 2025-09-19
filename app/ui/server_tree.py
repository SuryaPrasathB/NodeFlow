"""
A QTreeWidget for Browsing the OPC-UA Server's Node Structure.

This module provides the ServerTreeView, which lazily populates with nodes
from the connected OPC-UA server. It allows users to interact with nodes via a
context menu to add them to the dashboard or the sequencer.
"""
import logging
from asyncua import ua
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLineEdit, QTreeWidget, QTreeWidgetItem, QMenu, QApplication, QTreeWidgetItemIterator
from PyQt6.QtCore import Qt, pyqtSignal, QMimeData, QTimer
from PyQt6.QtGui import QAction, QDrag

class ServerTreeView(QWidget):
    """
    A widget that contains a search bar and a QTreeWidget for browsing an OPC-UA server.

    This class provides a hierarchical view of the OPC-UA server's address space.
    It populates the tree lazily, fetching child nodes only when a parent item is
    expanded. It also provides a context menu for interacting with nodes.

    Attributes:
        create_widget_requested (pyqtSignal): Emitted when a user requests to
            create a dashboard widget from a node. Passes the node's configuration (dict).
        add_to_sequencer_requested (pyqtSignal): Emitted when a user requests to
            add a method node to the sequencer. Passes the method's configuration (dict).
    """
    create_widget_requested = pyqtSignal(dict)
    add_to_sequencer_requested = pyqtSignal(dict)

    def __init__(self, opcua_logic, async_runner, parent=None):
        """
        Initializes the ServerTreeView.

        Args:
            opcua_logic (OpcuaClientLogic): The OPC-UA logic handler.
            async_runner (AsyncRunner): The utility for running async tasks.
            parent (QWidget, optional): The parent widget. Defaults to None.
        """
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

    def populate_root(self):
        """
        Clears the tree and populates it with the top-level nodes from the server's root.
        """
        self.tree_widget.clear()
        if self.opcua_logic.is_connected:
            root_node = self.opcua_logic.client.get_root_node()
            self.node_map.clear()
            root_item = QTreeWidgetItem(self.tree_widget, ["Root"])
            root_item.addChild(QTreeWidgetItem(["Loading..."]))
            self.node_map[id(root_item)] = root_node
            self.tree_widget.addTopLevelItem(root_item)
            self.async_runner.submit(self.populate_children(root_item, root_node))

    def on_item_expanded(self, item):
        """
        Lazily loads the children of an expanded item.

        Args:
            item (QTreeWidgetItem): The item that was expanded.
        """
        if item.childCount() > 0 and item.child(0).text(0) == "Loading...":
            node = self.node_map.get(id(item))
            if node and self.async_runner:
                self.async_runner.submit(self.populate_children(item, node))

    async def populate_children(self, parent_item, parent_node):
        """
        Asynchronously fetches and adds the children of a given node to the tree.

        Args:
            parent_item (QTreeWidgetItem): The item in the tree to add children to.
            parent_node (asyncua.Node): The OPC-UA node whose children to fetch.
        """
        try:
            children = await parent_node.get_children()
            if not children:
                children = await parent_node.get_referenced_nodes(
                    refs=ua.ObjectIds.HasSubtype,
                    direction=ua.BrowseDirection.Forward
                )
            parent_item.takeChildren()
            if not children: return

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
        Shows a context menu for the selected tree item.

        The options shown depend on the node type, which is determined asynchronously.

        Args:
            position (QPoint): The position where the context menu was requested.
        """
        item = self.tree_widget.itemAt(position)
        if not item: return
        node = self.node_map.get(id(item))
        if not node: return
        self.async_runner.submit(self.prepare_and_show_context_menu(node, position))

    async def prepare_and_show_context_menu(self, node, position):
        """
        Fetches node data asynchronously before showing the context menu.

        Args:
            node (asyncua.Node): The node for which to show the menu.
            position (QPoint): The position to show the menu at.
        """
        try:
            node_class = await node.read_node_class()
            QTimer.singleShot(0, lambda: self.show_context_menu(node, node_class, position))
        except Exception as e:
            logging.error(f"Could not build context menu: {e}")

    def show_context_menu(self, node, node_class, position):
        """
        Builds and shows the context menu with appropriate actions for the node type.

        Args:
            node (asyncua.Node): The node to create a menu for.
            node_class (ua.NodeClass): The class of the node.
            position (QPoint): The position to show the menu at.
        """
        context_menu = QMenu(self.tree_widget)
        if node_class in [ua.NodeClass.Variable, ua.NodeClass.Object]:
            add_widget_menu = context_menu.addMenu("Add as Widget")
            actions = {
                "Display (Numerical)": "Numerical Display", "Display (Text)": "Text Display",
                "Input (String)": "String Input", "Input (Numerical)": "Numerical Input",
                "Switch (Boolean)": "Switch"
            }
            for text, type_name in actions.items():
                action = QAction(text, self.tree_widget)
                action.triggered.connect(lambda checked, n=node, t=type_name: self.request_widget_creation(n, t))
                add_widget_menu.addAction(action)
        if node_class == ua.NodeClass.Method:
            add_to_seq_action = QAction("Add to Sequencer", self.tree_widget)
            add_to_seq_action.triggered.connect(lambda: self.request_sequencer_add(node))
            context_menu.addAction(add_to_seq_action)
            context_menu.addSeparator()
            button_action = QAction("Add as Button Widget", self.tree_widget)
            button_action.triggered.connect(lambda: self.request_widget_creation(node, "Button"))
            context_menu.addAction(button_action)
        if not context_menu.isEmpty():
            context_menu.exec(self.tree_widget.viewport().mapToGlobal(position))

    def request_widget_creation(self, node, widget_type):
        """Starts the process of creating a dashboard widget by gathering node info."""
        self.async_runner.submit(self.get_node_info_and_emit(node, widget_type))

    def request_sequencer_add(self, node):
        """Starts the process of adding a method node to the sequencer."""
        self.async_runner.submit(self.get_method_info_and_emit_for_sequencer(node))

    async def get_method_info_and_emit_for_sequencer(self, node):
        """Gathers info for a method node and emits the sequencer signal."""
        try:
            if await node.read_node_class() != ua.NodeClass.Method: return
            parent = await node.get_parent()
            bname = await node.read_browse_name()
            config = {"label": bname.Name, "identifier": parent.nodeid.to_string(), "method_bname": bname.Name}
            self.add_to_sequencer_requested.emit(config)
            logging.info(f"Requested to add '{bname.Name}' to sequencer.")
        except Exception as e:
            logging.error(f"Could not get method info for sequencer: {e}")

    async def get_node_info_and_emit(self, node, widget_type):
        """Gets node info and emits a signal to create a widget."""
        try:
            bname = await node.read_browse_name()
            config = {"widget_type": widget_type, "label": bname.Name, "search_type": "By Node ID"}
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
        """Filters the tree view based on the search text."""
        for i in range(self.tree_widget.topLevelItemCount()):
            self.filter_item(self.tree_widget.topLevelItem(i), text)

    def filter_item(self, item, text):
        """
        Recursively checks if an item or its children match the search text.

        Args:
            item (QTreeWidgetItem): The item to check.
            text (str): The search text.

        Returns:
            bool: True if the item or a child should be visible, False otherwise.
        """
        match = text.lower() in item.text(0).lower()
        child_match_found = any(self.filter_item(item.child(i), text) for i in range(item.childCount()))
        is_visible = match or child_match_found
        item.setHidden(not is_visible)
        if is_visible and child_match_found:
            item.setExpanded(True)
        return is_visible
