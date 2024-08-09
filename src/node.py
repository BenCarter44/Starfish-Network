import io
import pickle
from src.GraphEngine import auto_cutoff_recommend_random_path, recommend_random_path
from .SharedKV import *

CUSTOM_KEY = ">mem>"

MAX_PACKET_SIZE = 56 * 1024


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
        super().__init__(
            endpoint=DataTTL(endpoint, timeout=DEFAULT_TTL + time.time()),
            identity=DataTTL(identity, timeout=DEFAULT_TTL + time.time()),
        )

        self.global_key_value = KeyValueCommunications(
            serving_endpoint_query=endpoint, my_identity=identity
        )
        self.global_key_value.set_kv_raw(self.__kv_raw)
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
            """NOP"""
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

    def get_network_graph(self) -> nx.DiGraph:
        """Get graph representing all network connections between nodes.

        Returns:
            nx.DiGraph: Directed NetworkX Graph
        """
        return self.global_key_value.get_graph()

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

    def __kv_raw(
        self,
        dest: int,
        dat: bytes,
        c: int | None = None,
        p: int = 1,
        max_hop_count=10,
        resend=False,
        from_thread=False,
    ):
        """This function is to be a function pointer for the SharedKV engine.

        This function allows sending messages between peers that are initated from the
        SharedKV engine. Don't use this for anything else.

        Args:
            dest (int): Destination Node ID
            dat (bytes): Data in Bytes (small)
            c (int | None, optional): Communication ID. Defaults to Random ID.
            p (int, optional): Packet Number. Defaults to 1 (first packet).
            max_hop_count (int, optional): Max Hop Count. Defaults to 10.
            resend (bool, optional): Resend Request Flag. Defaults to False.
            from_thread (bool, optional): Flag from Thread Handling Receiving Communications. Defaults to False.
        """
        network = self.get_network_graph()
        path = list(
            auto_cutoff_recommend_random_path(
                network,
                self.identity.get_raw_val(),
                dest,
                max_hop_count,
            )
        )
        if len(path) == 0:
            return

        if c is None:
            # TODO: Do a better communication_identifier.
            c = random.randint(1, 2**32 - 1)

        self.debug_printf(f"PATH: {path}")
        self.__send_raw(dat, path, c, p, resend=resend, from_thread=from_thread)

    def send_data_to(
        self,
        dest_node: Node,
        data: io.BytesIO | io.BufferedRandom,
        max_hop_count: int = 10,
        find_routes: int = 5,
        resend: bool = False,
    ):
        """Send data to node using the node to node hops.

        Allows for peer-to-peer communication over any BytesIO/File Like object.

        Args:
            dest_node (Node): Node ID of destination
            data (io.BytesIO | io.BufferedRandom): File-Like Object
            max_hop_count (int, optional): Max number of hops of route. Defaults to 10.
            find_routes (int, optional): Min number of routes available. Defaults to 5.
            resend (bool, optional): Resend Request Flag. Defaults to False.

        Raises:
            ValueError: _description_
            ValueError: _description_
        """

        # First method:
        # use IP Graph. Traverse graph "randomly" until it reaches dest_node
        #
        # Second method: (synchronous)
        # Post Request For Data Send (Identity of dest, other stuff, session key)
        # Dest peer will see request and respond

        # The goal is to pick a set of identities and then pass packets through them

        network = self.get_network_graph()
        paths_raw: set[list[int]] = set()
        watch_dog = 0
        while len(paths_raw) < find_routes:
            path = tuple(
                auto_cutoff_recommend_random_path(
                    network,
                    self.identity.get_raw_val(),
                    dest_node.identity.get_raw_val(),
                    max_hop_count,
                )
            )
            if len(path) == 0:
                raise ValueError("Path Unreachable!")
                return
            paths_raw.add(path)  # type: ignore
            watch_dog += 1
            if watch_dog > find_routes * 20:
                raise ValueError("Too Few Routes")

        paths = list(paths_raw)
        counter = 0

        # TODO: Do a better communication_identifier.
        communication_identifier = random.randint(1, 2**32 - 1)

        inc = data.read(MAX_PACKET_SIZE)
        while True:
            if inc == b"":
                break
            counter += 1
            subject_path = paths[counter % len(paths)]
            self.debug_printf(f"Send on path {subject_path}: L: {len(inc)}")
            inc_new = data.read(MAX_PACKET_SIZE)
            self.__send_raw(
                inc,
                subject_path,
                communication_identifier,
                packet_number=counter,
                resend=resend,
                term=inc_new == b""
                and not (resend),  # check if inc is the last packet.
            )
            # move read packet to forward.
            inc = inc_new

    def __send_raw(
        self,
        data: bytes,
        path: list[int],
        comm_id: int,
        packet_number: int,
        term: bool = False,
        exp_len: Optional[int] = None,
        resend: bool = False,
        from_thread: bool = False,
    ):
        """Compile data into packet with destinations.

        Args:
            data (bytes): Packet data
            path (list[int]): Node ID path
            comm_id (_type_): Communication ID
            packet_number (int): Packet number
            term (bool, optional): Termination Flag. Defaults to False.
            exp_len (int, optional): Expected Message Length in Bytes. Defaults to None.
            resend (bool, optional): Resend Request Flag. Defaults to False.
            from_thread (bool, optional): From Receiving Thread Flag. Defaults to False.
        """
        end_envelope = Datagram(
            path[-1],
            data,
            comm_id,
            packet_number,
            author=self.identity.get_raw_val(),
            resend=resend,
        )
        cursor = end_envelope

        start = path[0]
        initial_send = path[1]
        for embed in reversed(path[2:]):
            cursor = Datagram(
                embed,
                cursor,
                comm_id=comm_id,
                packet=packet_number,
                term=term,
                exp_len=exp_len,
            )

        self.global_key_value.send_data(
            initial_send, cursor, data, from_thread=from_thread
        )

        # # For debugging!
        # print(f"Send from {start} to {initial_send} the following: ")
        # previous_node = path[1]
        # nest = 0
        # while True:
        #     print(f"{' '*nest}{cursor.data[0]}")
        #     if previous_node == cursor.get_to():
        #         break
        #     nest += 1
        #     d = cursor.get_data()
        #     previous_node = cursor.get_to()
        #     cursor = d

    def receiving_is_available(self) -> bool:
        """Have I received any data?"""
        inbox = self.global_key_value.get_inbox()

        return len(inbox) > 0

    def receiving_get_streams(self) -> dict[int, io.BytesIO | io.BufferedRandom]:
        """Return all IO messages received. (IO streams)

        Returns:
            dict[int, io.BytesIO | io.BufferedRandom]: Either BytesIO if small, or File-like Object
        """
        return self.global_key_value.get_inbox()

    def receiving_read(self, stream_id) -> io.BytesIO:
        """Returns the next in the queue if received data, else b''"""
        return self.global_key_value.get_inbox()[stream_id]

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
