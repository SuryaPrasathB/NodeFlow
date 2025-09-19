"""
Core OPC-UA Communication Logic.

This module provides the OpcuaClientLogic class, which encapsulates all
interactions with an OPC-UA server using the `asyncua` library. It handles
connecting, disconnecting, reading/writing values, calling methods, and managing
subscriptions. It is designed to be completely separate from the UI, ensuring
a clean separation of concerns.
"""
import asyncio
import logging
from asyncua import Client, ua
from asyncua.ua.uaerrors import UaError

class SubscriptionHandler:
    """
    Processes data change and status change notifications from an OPC-UA server subscription.

    An instance of this class is passed to the `asyncua` subscription handler.
    It receives callbacks from the server and forwards them to the main
    `OpcuaClientLogic` instance for dispatching.

    Args:
        logic_instance (OpcuaClientLogic): A reference to the main logic
            class to which notifications will be forwarded.
    """
    def __init__(self, logic_instance):
        """
        Initializes the SubscriptionHandler.

        Args:
            logic_instance (OpcuaClientLogic): A reference to the main logic
                class instance.
        """
        self.logic_instance = logic_instance

    def datachange_notification(self, node, val, data):
        """
        Handles data change notifications from the `asyncua` subscription.

        This method is called by `asyncua` whenever a subscribed node's value changes.
        It forwards the node and its new value to the logic instance for processing.

        Args:
            node (asyncua.Node): The node that triggered the notification.
            val: The new value of the node.
            data: The full data change notification object (not used).
        """
        asyncio.create_task(self.logic_instance.dispatch_data_change(node, val))

    def status_change_notification(self, status):
        """
        Handles subscription status change notifications.

        This is the primary mechanism for detecting a passive connection loss
        (e.g., network cable unplugged). If a bad status is received, it triggers
        the connection lost logic in the main client.

        Args:
            status (ua.StatusChangeNotification): The status change notification object.
        """
        logging.warning(f"Received a subscription status change notification: {status}")
        if status.Status.is_bad():
            logging.error("Subscription status is bad. Triggering connection lost logic.")
            if self.logic_instance.is_connected and self.logic_instance.connection_lost_callback:
                self.logic_instance.is_connected = False
                self.logic_instance.connection_lost_callback()

    def event_notification(self, event):
        """
        Handles event notifications from the server.

        Currently, this method only logs the received event.

        Args:
            event: The event notification object.
        """
        logging.info(f"Received event notification: {event}")


class OpcuaClientLogic:
    """
    Handles all business logic for interacting with an OPC-UA server.

    This class abstracts the complexities of the `asyncua` library into a set of
    async methods for connecting, disconnecting, reading, writing, and subscribing
    to nodes. It includes robust error handling and a mechanism for detecting
    connection loss.

    Attributes:
        client (asyncua.Client): The `asyncua` client instance.
        is_connected (bool): True if a connection is active, False otherwise.
        subscription (asyncua.Subscription): The subscription object.
        subscription_handler (SubscriptionHandler): The handler for subscription notifications.
        node_callback_map (dict): Maps subscribed nodes to their respective UI callbacks.
        connection_lost_callback (callable): A callback to be executed when the
                                             connection is lost.
    """
    def __init__(self):
        """Initializes the OpcuaClientLogic."""
        self.client = None
        self.is_connected = False
        self.subscription = None
        self.subscription_handler = None
        self.node_callback_map = {}
        self.connection_lost_callback = None

    async def connect(self, url, username=None, password=None):
        """
        Establishes a connection to the OPC-UA server.

        It creates a client instance, connects to the server, and sets up a
        subscription for data changes. If a client already exists, it is
        disconnected first to ensure a clean state.

        Args:
            url (str): The endpoint URL of the OPC-UA server.
            username (str, optional): The username for authentication. Defaults to None.
            password (str, optional): The password for authentication. Defaults to None.

        Returns:
            bool: True if the connection was successful.

        Raises:
            Exception: Propagates any exception that occurs during connection.
        """
        if self.client:
            logging.info("Existing client found. Disconnecting before creating a new connection.")
            await self.disconnect()

        try:
            self.client = Client(url=url, timeout=4)
            if username and password:
                self.client.set_user(username)
                self.client.set_password(password)

            await self.client.connect()
            self.is_connected = True

            self.subscription_handler = SubscriptionHandler(self)
            self.subscription = await self.client.create_subscription(500, self.subscription_handler)
            logging.info("OPC-UA Subscription created.")
            return True
        except Exception as e:
            self.client = None
            self.is_connected = False
            raise e

    async def disconnect(self):
        """
        Gracefully disconnects from the server and cleans up all resources.

        This includes deleting the subscription, disconnecting the client, and
        clearing any internal state.
        """
        if self.subscription:
            try:
                await self.subscription.delete()
            except Exception as e:
                logging.warning(f"Error deleting subscription: {e}")
            self.subscription = None

        if self.client and self.client.uaclient:
            try:
                await self.client.disconnect()
            except Exception as e:
                logging.warning(f"Error during disconnect: {e}")

        self.client = None
        self.is_connected = False
        self.node_callback_map.clear()

    async def _call_with_error_handling(self, coro):
        """
        A wrapper for network calls to provide centralized error handling.

        This wrapper catches common OPC-UA and network errors, triggers the
        connection lost callback if necessary, and re-raises the exception.

        Args:
            coro (coroutine): The awaitable object to execute.

        Returns:
            The result of the awaited coroutine.

        Raises:
            UaError: If an OPC-UA specific error occurs.
            asyncio.TimeoutError: If the operation times out.
            ConnectionError: If a general connection error occurs.
        """
        try:
            return await coro
        except (UaError, asyncio.TimeoutError, ConnectionError) as e:
            logging.error(f"OPC-UA operation failed: {e}. Connection may be lost.")
            if self.is_connected and self.connection_lost_callback:
                self.is_connected = False
                self.connection_lost_callback()
            raise

    async def subscribe_to_node_change(self, node, callback):
        """
        Subscribes to data changes for a specific node.

        Args:
            node (asyncua.Node): The node to subscribe to.
            callback (callable): The function to call when the node's value changes.
                                 This callback will receive the new value as its
                                 only argument.

        Returns:
            int: The subscription handle, which can be used to unsubscribe.
                 Returns None if no subscription is active.
        """
        if not self.subscription:
            logging.warning("Cannot subscribe, no active subscription exists.")
            return None

        self.node_callback_map[node] = callback
        handle = await self._call_with_error_handling(
            self.subscription.subscribe_data_change(node)
        )
        logging.info(f"Subscribed to node {node}. Handle: {handle}")
        return handle

    async def unsubscribe_from_node_change(self, node, handle):
        """
        Unsubscribes from data changes for a specific node.

        Args:
            node (asyncua.Node): The node to unsubscribe from.
            handle (int): The handle returned by `subscribe_to_node_change`.
        """
        if self.subscription and handle:
            await self._call_with_error_handling(
                self.subscription.unsubscribe(handle)
            )
            logging.info(f"Unsubscribed from node {node}. Handle: {handle}")

        if node in self.node_callback_map:
            del self.node_callback_map[node]

    async def dispatch_data_change(self, node, val):
        """
        Calls the appropriate callback for a data change notification.

        Args:
            node (asyncua.Node): The node whose value has changed.
            val: The new value of the node.
        """
        if node in self.node_callback_map:
            callback = self.node_callback_map[node]
            callback(val)
        else:
            logging.warning(f"Received data change for an unmapped node: {node}")

    async def find_node(self, identifier, search_type):
        """
        Finds a node on the server by its identifier.

        Note: `search_type` is not currently used but is kept for future-proofing.

        Args:
            identifier (str): The node identifier (e.g., "ns=2;i=123").
            search_type (str): The type of search (not currently used).

        Returns:
            asyncua.Node: The found node object.

        Raises:
            ConnectionError: If the client is not connected.
        """
        if not self.client:
            raise ConnectionError("Cannot find node, client is not connected.")
        return self.client.get_node(identifier)

    async def get_method_node(self, parent_node, method_bname):
        """
        Finds a method node by its browse name among the children of a parent node.

        Args:
            parent_node (asyncua.Node): The parent node (object) to search within.
            method_bname (str): The browse name of the method to find.

        Returns:
            asyncua.Node: The method node if found, otherwise None.
        """
        children = await self._call_with_error_handling(parent_node.get_children())
        for child_node in children:
            node_class = await child_node.read_node_class()
            if node_class == ua.NodeClass.Method:
                bname = await child_node.read_browse_name()
                if bname.Name == method_bname:
                    return child_node
        return None

    async def get_node_properties(self, node):
        """
        Reads the UserAccessLevel attribute of a node.

        Args:
            node (asyncua.Node): The node to read from.

        Returns:
            The value of the UserAccessLevel attribute.
        """
        return await self._call_with_error_handling(
             node.read_attribute(ua.AttributeIds.UserAccessLevel)
        )

    async def read_value(self, node):
        """
        Reads the value of a node.

        Args:
            node (asyncua.Node): The node to read from.

        Returns:
            The value of the node.
        """
        return await self._call_with_error_handling(node.read_value())

    async def write_value(self, node, value, datatype):
        """
        Writes a value to a node.

        Args:
            node (asyncua.Node): The node to write to.
            value: The value to write.
            datatype (ua.VariantType): The data type of the value.

        Returns:
            The result of the write operation.
        """
        variant = ua.Variant(value, datatype)
        return await self._call_with_error_handling(node.write_value(variant))

    async def call_method(self, parent_node_id, method_node_id, *args):
        """
        Calls a method on an OPC-UA object.

        Args:
            parent_node_id (str): The node ID of the parent object.
            method_node_id (str): The node ID of the method to call.
            *args: A variable number of arguments to pass to the method.

        Returns:
            The result of the method call.
        """
        parent_node = self.client.get_node(parent_node_id)
        return await self._call_with_error_handling(
            parent_node.call_method(method_node_id, *args)
        )
