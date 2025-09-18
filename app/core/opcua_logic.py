"""
Core OPC-UA Communication Logic.

This module provides the OpcuaClientLogic class, which encapsulates all
interactions with the OPC-UA server using the `asyncua` library. It handles
connecting, disconnecting, reading/writing values, calling methods, and managing
subscriptions. It is designed to be completely separate from the UI.
"""
import asyncio
import logging
from asyncua import Client, ua
from asyncua.ua.uaerrors import UaError

class SubscriptionHandler:
    """
    Processes data change notifications from the OPC-UA server.
    An instance of this class is passed to the asyncua subscription handler.
    """
    def __init__(self, logic_instance):
        """
        Initializes the handler.

        Args:
            logic_instance (OpcuaClientLogic): A reference to the main logic
                class to forward notifications.
        """
        self.logic_instance = logic_instance

    def datachange_notification(self, node, val, data):
        """
        Callback method called by asyncua when a subscribed node's value changes.
        """
        # Forward the notification to the main logic class to be dispatched
        # to the correct widget.
        asyncio.create_task(self.logic_instance.dispatch_data_change(node, val))

    def status_change_notification(self, status):
        """
        Callback method called by asyncua when the subscription status changes.
        This is the primary mechanism for detecting passive connection loss.
        """
        logging.warning(f"Received a subscription status change notification: {status}")
        # If the status is bad (e.g., timeout), it's a strong indicator the connection is lost.
        ## MODIFIED ##
        # The StatusChangeNotification object contains a 'Status' attribute which is a StatusCode object.
        # We must call is_bad() on the StatusCode object itself.
        if status.Status.is_bad():
            logging.error("Subscription status is bad. Triggering connection lost logic.")
            # Check if we are still marked as connected to avoid multiple calls
            if self.logic_instance.is_connected and self.logic_instance.connection_lost_callback:
                # Set connected status to false immediately to prevent race conditions
                self.logic_instance.is_connected = False
                self.logic_instance.connection_lost_callback()

    def event_notification(self, event):
        """
        Callback method for OPC-UA events. Currently logs only.
        """
        logging.info(f"Received event notification: {event}")


class OpcuaClientLogic:
    """
    Handles all business logic for interacting with an OPC-UA server.
    Includes connection management, subscriptions, and robust error handling.
    """
    def __init__(self):
        self.client = None
        self.is_connected = False
        self.subscription = None
        self.subscription_handler = None
        self.node_callback_map = {}
        self.connection_lost_callback = None

    async def connect(self, url, username=None, password=None):
        """
        Establishes a connection to the OPC-UA server and creates a subscription.
        If a client already exists, it will be fully disconnected first to ensure a clean state.
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
        """Gracefully disconnects from the server and cleans up resources."""
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
        A wrapper for all network calls to provide centralized error handling
        and connection loss detection.
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
        if self.subscription and handle:
            await self._call_with_error_handling(
                self.subscription.unsubscribe(handle)
            )
            logging.info(f"Unsubscribed from node {node}. Handle: {handle}")

        if node in self.node_callback_map:
            del self.node_callback_map[node]

    async def dispatch_data_change(self, node, val):
        if node in self.node_callback_map:
            callback = self.node_callback_map[node]
            callback(val)
        else:
            logging.warning(f"Received data change for an unmapped node: {node}")

    async def find_node(self, identifier, search_type):
        if not self.client:
            raise ConnectionError("Cannot find node, client is not connected.")
        return self.client.get_node(identifier)

    async def get_method_node(self, parent_node, method_bname):
        children = await self._call_with_error_handling(parent_node.get_children())
        for child_node in children:
            node_class = await child_node.read_node_class()
            if node_class == ua.NodeClass.Method:
                bname = await child_node.read_browse_name()
                if bname.Name == method_bname:
                    return child_node
        return None

    async def get_node_properties(self, node):
        return await self._call_with_error_handling(
             node.read_attribute(ua.AttributeIds.UserAccessLevel)
        )

    async def read_value(self, node):
        return await self._call_with_error_handling(node.read_value())

    async def write_value(self, node, value, datatype):
        variant = ua.Variant(value, datatype)
        return await self._call_with_error_handling(node.write_value(variant))

    async def call_method(self, parent_node_id, method_node_id, *args):
        parent_node = self.client.get_node(parent_node_id)
        return await self._call_with_error_handling(
            parent_node.call_method(method_node_id, *args)
        )
