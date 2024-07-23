from .SharedKV import *

CUSTOM_KEY = ">mem>"


class Node:
    """Overarching Node Object"""

    def __init__(
        self,
        endpoint: DataTTL | None = None,
        identity: DataTTL | None = None,
    ) -> None:
        """Create Node. Set attributes (endpoint, identity) as necessary"""
        if endpoint is None:
            endpoint = DataTTL(None, 0, True)
        if identity is None:
            identity = DataTTL(None, 0, True)

        self.endpoint: DataTTL = endpoint
        self.identity: DataTTL = identity


class Owned_Node(Node):
    """A node that is controlled or hosted by a user

    Args:
        Node (_type_): _description_
    """

    def __init__(self, endpoint: str, identity: int) -> None:
        """Setup a node hosted by the user

        Args:
            endpoint (str): Endpoint serving
            identity (int): Identity of the user.
        """
        super().__init__()

        self.global_key_value = KeyValueCommunications(
            serving_endpoint_query=endpoint, my_identity=identity
        )
        self.receiving_queue: list[bytes] = []

    def connect_to_node(self, dest_node: Node):
        """Connect to node"""
        try:
            endpt = dest_node.endpoint.get_value()  # type: ignore
        except:
            raise ValueError("Node does not have current endpoint set")

        self.global_key_value.connect_to_peer(endpt)

    def disconnect_from_node(self, dest_node: Node):
        """Disconnect from node"""
        try:
            endpt = dest_node.endpoint.get_value()  # type: ignore
        except:
            raise ValueError("Node does not have current endpoint set")

        self.global_key_value.disconnect_from_peer(endpt)

    def stop_communications(self):
        """Stop and shutdown node"""
        self.global_key_value.stop()

    def get_global_key_values(self) -> DataTTL_Library:
        """Get global dictionary. TODO."""

        def blank(s: str, d: DataTTL):
            pass

        return DataTTL_Library(blank)

    def get_global_node_network_by_endpoint(self) -> list[Node]:
        """Get all nodes in the network by IPs

        Returns:
            list[DataTTL]: _description_
        """
        keys = self.global_key_value.get_keys()

        out = []
        for row in keys:
            path = row.split(">")
            if len(path) != 3:
                continue
            if path[1] != "ip":
                continue

            out.append(Node(endpoint=self.global_key_value.get(row)))
        return out

    def get_global_node_network_by_identity(self) -> list[Node]:
        """Get all nodes in the network by identities

        Returns:
            list[DataTTL]: _description_
        """
        keys = self.global_key_value.get_keys()

        out = []
        for row in keys:
            path = row.split(">")
            if len(path) != 3:
                continue
            if path[1] != "id_graph":
                continue

            out.append(Node(identity=self.global_key_value.get(row)))
        return out

    def get_inbound_connected_nodes(self) -> list[Node]:
        """Get inbound connected nodes"""
        # query inbound_peers

        connections = self.global_key_value.get_inbound_connections()

        out = []
        for node in connections:
            endpoint = node[0]
            identity = node[1]
            out.append(Node(endpoint=endpoint, identity=identity))
        return out

    def get_outbound_connected_nodes(self) -> list[Node]:
        """Get outbound connected nodes"""

        endpoints = self.global_key_value.get_outbound_endpoints()

        out = []
        for endpoint in endpoints:
            out.append(Node(endpoint=endpoint))

        return out

    def debug_printf(self, msg, end: str = "\n"):
        """Debug print with color based on the identity.

        Args:
            msg (Any): What to print.
            end (str): What to place at the end of line. Defaults to '\n'
        """
        self.global_key_value.printf(msg, end)

    def debug_dump_kv(self):
        """Dump the global key-value store."""
        self.debug_printf(self.global_key_value.string_print_endpoint_kv())

    # =========== Memory (key-value) =====================
    def set(self, key: str, val: Any, ttl: Optional[float] = DEFAULT_TTL):
        """Set value in memory

        Args:
            key (str): _description_
            val (Any): _description_
            ttl (Optional[float], optional): _description_. Defaults to None.
        """
        self.global_key_value.set(kv_key(CUSTOM_KEY, key), val, ttl)

    # =========== Data Passing ===========================

    def send_data_to(self, dest_node: Node, data: bytes):
        """Send data to node."""
        # TODO.

    def receiving_is_available(self) -> bool:
        """Have I received any data?"""
        return len(self.receiving_queue) > 0

    def receiving_read(self) -> bytes:
        """Returns the next in the queue if received data, else b''"""
        if not (self.receiving_is_available()):
            return b""
        out = self.receiving_peek()
        self.receiving_queue.pop(0)
        return out

    def receiving_peek(self) -> bytes:
        """Same as read, but does not advance the Queue"""
        return self.receiving_queue[0]

    # ========== File Support ============================

    def fetch_file(self, file_id) -> bytes:
        """Fetch a file from the file distributed store"""
        # TODO.
        return b""

    def store_file(self, file_id, file_bytes):
        # TODO.
        """Store file on the file distributed store"""

    # ========= DNS (Friendly Name Server) Support =======

    def lookup_identity(self, nice_name) -> str:
        # TODO.
        """Get node identity based on the identity"""
        return ""
