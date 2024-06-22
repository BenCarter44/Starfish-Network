import datetime
import random
import threading
import time
from typing import Any, Dict, List, Set, Union, cast
import zmq

from src.MessageFormats import *
from src.ReliabilityEngine import *
from src.ttl import DataTTL_Library, DataTTL

DEFAULT_TTL = 5
IDENTITY_TTL = 60 * 60

IP_KEY = ">ip>"
IDENTITY_KEY = ">id_graph>"


def kv_key(root: str, key: Any):
    """Concat key path to root

    Args:
        root (str): Root path
        key (Any): Key path

    Returns:
        str: combined path
    """
    return root + str(key)


class ConnectedPeers_Dealer:
    """Struct holding connected_socket information"""

    def __init__(
        self,
        re: ReliabilityEngine,
        out: zmq.Socket,
        last_seen: float = time.time(),
        avg: float = DEFAULT_TTL,
    ):
        """Struct holding connected_socket information from DEALER

        Args:
            re (ReliabilityEngine): Reliability Engine socket
            out (zmq.Socket): Output PIPE from Reliability Engine
            last_seen (float, optional): Timestamp of last seen. Defaults to time.time().
            avg (float, optional): Average in seconds between requests. Defaults to DEFAULT_TTL.
        """
        self.rsoc = re
        self.out = out
        self.last_seen = last_seen
        self.avg = avg


class InboundPeers_Router:
    """Struct holding socket information from ROUTER"""

    def __init__(
        self,
        addr: bytes,
        endpt: str,
        last_seen: float = time.time(),
        avg: float = DEFAULT_TTL,
    ):
        """Struct holding socket information from ROUTER

        Args:
            addr (bytes): Address of sender by ZMQ
            endpt (str): Endpoint
            last_seen (float, optional): Timestamp of peer last seen. Defaults to time.time().
            avg (float, optional): Average time between requests. Defaults to DEFAULT_TTL.
        """
        self.addr = addr
        self.endpoint = endpt
        self.last_seen = last_seen
        self.avg = avg


class KeyValueCommunications:
    """Main KeyValue Class - Manages all Shared K-V Memory and peer-to-peer connections"""

    def __init__(self, serving_endpoint_query: str, my_identity: int):
        """Create peer at endpoint with identity

        Args:
            serving_endpoint_query (str): Endpoint
            my_identity (int): identity
        """
        self.context = zmq.Context()
        self.my_identity = my_identity
        self.serving_endpoint_query = serving_endpoint_query
        # self.ttl = 60 + time.time() # TODO: Implement heart beating and real TTLs.
        # sockets for binding to receive connections from peers

        self.receive_query_socket = self.context.socket(zmq.ROUTER)
        self.receive_query_socket.bind(serving_endpoint_query)

        # # self.peer_subscribe_socket.setsockopt(zmq.IDENTITY,my_identity)

        # TODO: Design Decision: Dealer sends communications to ALL connected peers

        # TODO: Identity is not required here. (Key Value doesn't have identity.)

        # self.endpoints_kv : Dict[str, DataWithTTL] = {} # IP is key. TTL is value.
        self.endpoints_kv: DataTTL_Library = DataTTL_Library(self.__send_update)

        self.connected_peers: Set[str] = set()  # outbound connections!
        self.connected_sockets: Dict[str, ConnectedPeers_Dealer] = (
            {}
        )  # outbound connections!

        # inbound connections!
        self.inbound_peers: dict[str, InboundPeers_Router] = {}
        self.inbound_peers_addr: dict[bytes, InboundPeers_Router] = {}

        self.new_data = False
        # do not add yourself, others will tell you the TTL.

        self.control_socket_outside, inside_socket = zpipe(self.context)

        self.open_messages: Dict[str, ReliableMessage] = {}
        self.open_message_data: Dict[str, Any] = {}

        self.th = threading.Thread(
            None,
            self.__handle_responses,
            args=(inside_socket,),
            name=f"KeyVal Management {my_identity}",
        )
        self.th.start()

    def printf(self, msg: Any, end="\n"):
        """Pretty print based on identity color

        Args:
            msg (Any): Message to print
            end (str, optional): Ending separator. Defaults to "\n".
        """
        colors = {
            101: 93,
            102: 137,
            103: 75,
            104: 28,
            105: 168,
            106: 106,
            107: 107,
            108: 108,
            109: 109,
            110: 110,
        }
        color_print = f"\033[38;5;{colors[self.my_identity]}m"
        color_stop = "\033[0m"
        print(
            f"{color_print}Node {self.my_identity} | {datetime.datetime.now()} : {msg}{color_stop}",
            end=end,
        )

    # TODO: Structure:
    #   Interface:
    #       connect to peer
    #       get endpoints
    #       get connected peers
    #       disconnect from peer
    #       stop
    #
    #   Protocol Methods:
    #       send_hello() / finish_hello()
    #       send_state_request() / finish_state_request()
    #       push_peer_updates()
    #       push_new_value()
    #
    #   Receiving methods:
    #       receiving_hello()
    #       answer_state_request()
    #       subscribed_updates()
    #       answer_new_value()
    #
    #
    #   Thread methods:
    #      handle_responses()
    #          delegates receiving msgs to the receiving methods
    #
    #   Reliability Engine
    #      needs it's own class....
    #      reliable_message = add_message(msg, retry_gap=10sec, max_retry=5)
    #      reliable_message.mark_done()
    #      reliable_message.is_complete()
    #

    def connect_to_peer(self, endpoint_query: str, block=True):
        """Connect to peer at endpoint_query

        Args:
            endpoint_query (str): Endpoint
            block (bool, optional): Wait for steps to complete. Defaults to True.
        """

        if f"{endpoint_query}" in self.connected_peers:
            self.printf("Already connected to Peer! Aborting")
            return

        socket = self.context.socket(zmq.DEALER)
        socket.setsockopt(
            zmq.IDENTITY, str(self.my_identity).encode("utf-8")
        )  # TODO: Set ID as key.
        output, b = zpipe(self.context)
        self.connected_sockets[endpoint_query] = ConnectedPeers_Dealer(
            ReliabilityEngine(self.context, socket, b), output
        )
        self.control_socket_outside.send_multipart(
            [b"connect", endpoint_query.encode("utf-8")]
        )
        # TODO. Move connected_sockets into a separate struct and open_message_data
        i = self.connected_sockets[endpoint_query].rsoc.get_number_peers()
        i2 = i
        self.connected_sockets[endpoint_query].rsoc.add_peer(endpoint_query)
        while i == i2:  # wait for connect.
            i2 = self.connected_sockets[endpoint_query].rsoc.get_number_peers()
            time.sleep(0.001)

        # connected! Send hello!
        reply_id = self.__send_hello(endpoint_query, not (block))

        # wait for it to be done!
        while not (
            cast(dict[str, bool], self.open_message_data[f"hello-{reply_id}"])["done"]
        ):
            if not (block):
                break
            time.sleep(0.01)  # try every 10 msec

        if not (block):
            return

        reply_id = self.__send_state_request(endpoint_query)

        # wait for it to be done!
        while not (
            cast(dict[str, bool], self.open_message_data[f"state-{reply_id}"])["done"]
        ):
            time.sleep(0.01)  # try every 10 msec

        reply_id = self.__send_request_connection(endpoint_query)

        # wait for it to be done!
        while not (
            cast(dict[str, bool], self.open_message_data[f"send-request-{reply_id}"])[
                "done"
            ]
        ):
            time.sleep(0.01)  # try every 10 msec

    def disconnect_from_peer(self, endpoint_query: str, skip=False):
        """Disconnect from peer

        Args:
            endpoint_query (str): Endpoint to disconnect from
            skip (bool, optional): Skip requesting peer to disconnect with us. Defaults to False.
        """
        if endpoint_query not in self.connected_peers:
            self.printf(f"Error - already disconnected from {endpoint_query}")
            return
        if not (skip):
            self.__send_disconnect_request(endpoint_query)
            time.sleep(0.1)
        self.connected_peers.remove(endpoint_query)
        self.connected_sockets[endpoint_query].rsoc.remove_peer(endpoint_query)
        self.control_socket_outside.send_multipart(
            [b"disconnect", endpoint_query.encode("utf-8")]
        )
        self.printf(f"Disconnected from {endpoint_query}")

    def stop(self):
        """Stop thread and shutdown peer"""
        for peer in list(self.connected_peers):
            self.disconnect_from_peer(peer, True)
        self.control_socket_outside.send_multipart([b"STOP"])
        self.th.join()

    def endpoints_modified(self) -> bool:
        """Depreciated: flag if endpoints modified

        Returns:
            _type_: _description_
        """
        i = self.new_data
        return i

    def reset_modify(self):
        """Depreciated: set flag to false for endpoint modification"""
        self.new_data = False

    def pretty_print_endpoint_kv(self, title="Endpoints:"):
        """Print key-value library to console

        Args:
            title (str, optional): Title at top of table. Defaults to "Endpoints:".
        """
        print(self.string_print_endpoint_kv(title))

    def string_print_endpoint_kv(self, title="Endpoints:") -> str:
        """Format keyvalue into human-readable string

        Args:
            title (str, optional): _description_. Defaults to "Endpoints:".

        Returns:
            str: formatted string
        """

        def sfill(s: Any, l: int) -> str:
            """Cast and fill string with spaces until string is at length l

            Args:
                s (str): string
                l (int): length of string

            Returns:
                str: String with filled spaces
            """
            s = str(s)
            while len(s) < l:
                s = s + " "
            return s

        out_debug = title + "\n"
        out_debug += "\t IP \t\t\t | \t IP-val \t\t\t | \t EXP \t \n"
        keys = list(self.endpoints_kv.get_keys())
        keys.sort()
        for x in keys:
            out_debug += f"{sfill(x, 35)} | "
            endpt: DataTTL = self.endpoints_kv.get_data(x)
            out_debug += f"{sfill(endpt.get_value_or_null(), 30)} | {sfill(datetime.datetime.fromtimestamp(endpt.get_timeout()), 23)}   | \n"

        return out_debug

    def set(self, key: str, val: Any, ttl: Optional[float] = None):
        """Set key in library to a certain value

        Args:
            key (str): Key string
            val (Any): Value
            ttl (Optional[float], optional): Time to live timestamp. Defaults to None.
        """
        # I now know endpoint!
        if ttl is None:
            ttl = DEFAULT_TTL + time.time()
        d = DataTTL(val, ttl)
        self.endpoints_kv.merge(key, d)

    def get(self, key: str) -> Any:
        """Get value from key

        Args:
            key (str): Key

        Returns:
            Any: Vale

        Raises:
            KeyError: If key not found
        """
        return self.endpoints_kv.get_data(key)

    def has(self, key: str) -> bool:
        """See if key is currently active

        Args:
            key (str): key

        Returns:
            bool: True if active
        """
        return self.endpoints_kv.has(key)

    def get_keys(self) -> Any:
        """Get list of keys available

        Returns:
            dict_keys[str, DataWithTTL]: list of keys available
        """
        return self.endpoints_kv.get_keys()

    # Protocol Methods -------------------------------- No blocking allowed in all finishes.
    # All finishes too must be idempotent (assume req's are replayed)

    def __send_hello(self, endpoint: str, auto_state=False) -> int:
        """Send hello message to endpoint

        Args:
            endpoint (str): Endpoint string
            auto_state (bool, optional): True to automatically send state request afterwards. Defaults to False.

        Returns:
            int: Reply Identity
        """
        reply_id = random.randint(0, 32766)
        while (
            f"hello-{reply_id }" in self.open_messages
        ):  # TODO: Instead of R, do hash of data.
            reply_id = random.randint(0, 32766)

        self.open_message_data[f"hello-{reply_id }"] = {
            "query": endpoint,
            "done": False,
        }
        if auto_state:
            self.open_message_data[f"hello-{reply_id}"]["next-state"] = True
        # TODO: Design Decision. Currently, this will be sent to ALL connected peers (dealer socket)
        msg = PeerKV_Hello()

        msg.create(reply_id, self.serving_endpoint_query)
        self.printf(
            f"Sending hello message with r:{reply_id}"
        )  # TODO. DEALER socket distributes requests... this means that it must be repeated.

        rm = self.connected_sockets[endpoint].rsoc.add_message(msg.compile(), 10, 25)
        if rm is None:
            raise ValueError("RM is NONE!")  # todo here.
        self.open_messages[f"hello-{reply_id}"] = rm
        return reply_id

    def __receiving_hello(self, msg: PeerKV_Hello, address: bytes):
        """Process received hello request

        Args:
            msg (PeerKV_Hello): Hello Message
            address (bytes): Address of sender
        """
        # store address/ip in lookup table for mark use
        endpoint = msg.get_endpoint()

        # I now know endpoint!
        self.set(kv_key(IP_KEY, endpoint), f"a{time.time()}")

        # doesn't matter for retries.
        pk_response = PeerKV_Hello()
        pk_response.create_welcome(msg.get_r_identity())

        base = kv_key(IDENTITY_KEY, self.my_identity)
        self.set(base, f"{self.my_identity} + LIMIT", ttl=IDENTITY_TTL + time.time())
        self.set(
            kv_key(base + ">", address.decode("utf-8")),
            address.decode("utf-8") + " LAT",
        )

        self.inbound_peers[endpoint] = InboundPeers_Router(address, endpoint)

        self.inbound_peers_addr[address] = self.inbound_peers[endpoint]

        self.printf(
            f"Received hello. Send hello response to {endpoint} with r:{pk_response.get_r_identity()}"
        )
        self.receive_query_socket.send_multipart(
            pk_response.compile_with_address(address)
        )

    def __finish_hello(self, msg: PeerKV_Hello):
        """Finish hello sequence

        Args:
            msg (PeerKV_Hello): ACK Message
        """
        r = msg.get_r_identity()
        if self.open_messages[f"hello-{r}"].is_complete():
            return  # don't need to answer. Already received response
        self.open_messages[f"hello-{r}"].mark_done()
        request_data = cast(dict[str, Any], self.open_message_data[f"hello-{r}"])
        endpoint = request_data["query"]

        self.connected_sockets[endpoint].last_seen = time.time()
        self.connected_peers.add(endpoint)

        self.printf(f"Finished Hello. Recv'ed response with r:{msg.get_r_identity()}")

        request_data["done"] = True  # passes by ref.
        if "next-state" in request_data:
            self.__send_state_request(endpoint)

    def __send_state_request(self, endpoint: str) -> int:
        """Send state request to endpoint

        Args:
            endpoint (str): Endpoint

        Returns:
            int: Reply Identity
        """

        reply_id = random.randint(0, 32766)
        while (
            f"state-{reply_id }" in self.open_messages
        ):  # TODO: Instead of R, do hash of data.
            reply_id = random.randint(0, 32766)

        self.open_message_data[f"state-{reply_id}"] = {"done": False}
        pk = PeerKV()
        pk.fetch_state_command(r_identity=reply_id)
        self.printf(f"Send State Request r:{endpoint}")
        rm = self.connected_sockets[endpoint].rsoc.add_message(pk.compile(), 10, 5)
        if rm is None:
            raise ValueError("RM none 2")
        self.open_messages[f"state-{reply_id}"] = cast(ReliableMessage, rm)
        return reply_id

    def __receive_state_request(self, msg: PeerKV, address: bytes):
        """Receive state request from address

        Args:
            msg (PeerKV): Message
            address (bytes): Address
        """
        self.printf(f"Received State Request r:{msg.get_r_identity()}")

        pk_response = PeerKV()
        results = []
        # self.printf("Sending: ")
        for key in self.endpoints_kv.get_keys():  # general. Transfer all keys
            dat = self.endpoints_kv.get_data(key)
            v = dat.get_value_or_null()
            if v is not None:
                results.append((key, dat))
                # print(key, ":", v, datetime.datetime.fromtimestamp(dat.get_timeout()))

        self.printf(f"Send State Response to PEER r:{msg.get_r_identity()}")
        pk_response.return_state_receipt(results, msg.get_r_identity())
        self.receive_query_socket.send_multipart(
            pk_response.compile_with_address(address)
        )

    def __finish_state_request(self, msg: PeerKV):
        """Finish state request sequence

        Args:
            msg (PeerKV): Message ACK message
        """
        state = msg.get_state_from_return()
        if self.open_messages[f"state-{msg.get_r_identity()}"].is_complete():
            self.printf(
                f"Finish State Req - message already received. Drop r:{msg.get_r_identity()}"
            )
            return  # don't need to answer. Already received response due to dealer.

        # merge the key values together.
        # self.printf("Received: ")
        for state_val in state:
            key = state_val[0]
            val = state_val[1]
            # print(key,":", val.get_value_or_null(), datetime.datetime.fromtimestamp(val.get_timeout()))
            self.endpoints_kv.merge(key, val)

        self.printf(f"Finish State Req. Recv'd response :{msg.get_r_identity()}")
        r = msg.get_r_identity()
        self.open_messages[f"state-{r}"].mark_done()
        request_data = cast(dict[str, bool], self.open_message_data[f"state-{r}"])
        request_data["done"] = True

    def __send_request_connection(self, endpoint: str) -> int:
        """Send request connection to endpoint

        Args:
            endpoint (str): Endpoint

        Returns:
            int: Reply Identity
        """
        reply_id = random.randint(0, 32766)
        while (
            f"send-request-{reply_id}" in self.open_messages
        ):  # TODO: Instead of R, do hash of data.
            reply_id = random.randint(0, 32766)

        self.printf(f"Sending a connection request to {endpoint} with r:{reply_id}")
        self.open_message_data[f"send-request-{reply_id}"] = {"done": False}
        pk = PeerKV()
        pk.request_connection_cmd(reply_id)
        rm = self.connected_sockets[endpoint].rsoc.add_message(pk.compile(), 10, 5)
        if rm is None:
            raise ValueError("Rm is none 545")
        self.open_messages[f"send-request-{reply_id}"] = cast(ReliableMessage, rm)

        return reply_id

    def __receive_request_for_connection(self, msg: PeerKV, address: bytes):
        """Receive connection request

        Args:
            msg (PeerKV): Message
            address (bytes): Address of sender
        """
        reply_identity = msg.get_r_identity()
        endpoint = self.inbound_peers_addr[address].endpoint
        self.printf(
            f"Received a connection request from {endpoint} with r:{reply_identity}"
        )

        pk = PeerKV()
        self.printf(
            f"Send response to connection request from {endpoint} with r:{reply_identity}"
        )
        pk.request_connection_feedback(reply_identity)
        self.receive_query_socket.send_multipart(pk.compile_with_address(address))

        # connect to peer! Will take a second.... (async)
        self.connect_to_peer(endpoint, False)

    def __send_disconnect_request(self, endpoint: str):
        """Send disconnect request

        Args:
            endpoint (str): _description_

        Returns:
            _type_: _description_
        """
        reply_id = random.randint(0, 32766)
        while (
            f"disconn-send-request-{reply_id}" in self.open_messages
        ):  # TODO: Instead of R, do hash of data.
            reply_id = random.randint(0, 32766)

        self.printf(f"Sending a disconnection request to {endpoint} with r:{reply_id}")
        self.open_message_data[f"disconn-send-request-{reply_id}"] = {"done": False}
        pk = PeerKV()
        pk.request_disconnect(reply_id)
        rm = self.connected_sockets[endpoint].rsoc.add_message(pk.compile(), 0.1, 5)
        if rm is None:
            raise ValueError("RM is none!")
        self.open_messages[f"disconn-send-request-{reply_id}"] = cast(
            ReliableMessage, rm
        )
        return reply_id

    def __receive_disconnect_request(self, msg: PeerKV, addr: bytes):
        """Receive disconnection request

        Args:
            msg (PeerKV): _description_
            addr (bytes): _description_
        """
        endpoint = self.inbound_peers_addr[addr].endpoint
        self.printf(
            f"Received a disconnection request from {endpoint} with r:{msg.get_r_identity()}"
        )
        self.disconnect_from_peer(endpoint, skip=True)
        del self.inbound_peers_addr[addr]

    def __finish_request_for_connection(self, msg: PeerKV):
        """Finish request for connection sequence

        Args:
            msg (PeerKV): ACK Message
        """
        r = msg.get_r_identity()
        if self.open_messages[f"send-request-{r}"].is_complete():
            return  # don't need to answer. Already received response
        self.open_messages[f"send-request-{r}"].mark_done()
        request_data = self.open_message_data[f"send-request-{r}"]
        request_data = cast(dict[str, bool], request_data)
        self.printf(
            f"Finished Request for connection. Recv'ed response with r:{msg.get_r_identity()}"
        )

        request_data["done"] = True  # passes by ref.

    def __is_alive(self, endpoint: str, address: Optional[bytes] = None, dealer=False):
        """Update keyvalues to say endpoint/address is alive

        Args:
            endpoint (str): Endpoint
            address (bytes, optional): Address. Defaults to None.
            dealer (bool, optional): True if Dealer. Defaults to False.

        Raises:
            ValueError: If no address is given in router mode
                        (requires either endpoint or address)

        """
        # outbound means from dealer
        # update endpoint's TTL with new value.

        if dealer and endpoint not in self.connected_peers:
            self.printf("Isalive: Dealer got feedback while dealer never said hello!")
            return

        if not (dealer) and endpoint not in self.inbound_peers:
            self.printf("Isalive: Client connected without saying hello first!")
            return

        if not (dealer) and address is None:
            raise ValueError("Require Address")

        # self.printf("Running is alive")

        ttl = DEFAULT_TTL + time.time()
        if dealer:
            last_seen = self.connected_sockets[endpoint].last_seen
            avg = self.connected_sockets[endpoint].avg
            avg = (avg * 0.30) + (time.time() - last_seen) * 0.70

            # self.printf(f"D - Last seen for {endpoint}: {datetime.datetime.fromtimestamp(last_seen)}")
            # self.printf(f"D - Avg for {endpoint}: {avg}")
            self.connected_sockets[endpoint].last_seen = time.time()
            self.connected_sockets[endpoint].avg = avg

            a: float = 0
            if avg > 3600:
                a = 3600
            else:
                a = avg

            multiplier = 60 * pow(2, -0.2 * avg) + 1

            ttl = time.time() + a * multiplier

            if ttl - time.time() > 86400:
                ttl = time.time() + 86400
            elif ttl - time.time() < 1:
                ttl = time.time() + 2
            # self.printf(f"Calc for ttl: {datetime.datetime.fromtimestamp(ttl)}")

        else:
            address = cast(bytes, address)
            last_seen = self.inbound_peers[endpoint].last_seen
            avg = self.inbound_peers[endpoint].avg
            # self.printf(f"R - Last seen for {endpoint}: {datetime.datetime.fromtimestamp(last_seen)}")
            # self.printf(f"R - Avg for {endpoint}: {avg}")
            avg = (avg * 0.80) + (time.time() - last_seen) * 0.20

            self.inbound_peers[endpoint].last_seen = time.time()
            self.inbound_peers[endpoint].avg = avg

            a = 0
            if avg > 3600:
                a = 3600
            else:
                a = avg

            multiplier = 60 * pow(2, -0.2 * avg) + 1

            ttl = time.time() + a * multiplier

            if ttl - time.time() > 86400:
                ttl = time.time() + 86400
            elif ttl - time.time() < 1:
                ttl = time.time() + 2
            # self.printf(f"Calc for ttl: {datetime.datetime.fromtimestamp(ttl)}")

            base = kv_key(IDENTITY_KEY, self.my_identity)
            # self.printf(f"{ttl}, {time.time()}, {ttl - time.time()}, {kv_key(IP_KEY,endpoint)}")
            self.set(
                kv_key(base + ">", address.decode("utf-8")),
                address.decode("utf-8") + " latency",
                ttl,
            )

        self.set(kv_key(IP_KEY, endpoint), f"abc{time.time()}", ttl)
        # self.printf("Finish keep alive")

    def __send_update(self, key: str, data: DataTTL):
        """Send update of keyvalue to peers

        Args:
            key (str): key
            data (DataWithTTL): data
        """
        for peer in self.connected_peers:
            reply_id = random.randint(0, 32766)
            while (
                f"update-{reply_id }" in self.open_messages
            ):  # TODO: Instead of R, do hash of data.
                reply_id = random.randint(0, 32766)

            msg = PeerKV()
            msg.push_change(key, data, reply_id)
            self.printf(
                f"Post update r:{reply_id} of [{key}]={data.get_value_or_null()} Timeout: {datetime.datetime.fromtimestamp(data.get_timeout())}- send to {peer}"
            )

            rm = self.connected_sockets[peer].rsoc.add_message(msg.compile())
            if rm is None:
                self.printf("None found -- skip")
                continue
            self.open_messages[f"update-{reply_id}"] = cast(ReliableMessage, rm)

    def __receive_update(self, msg: PeerKV, address: bytes):
        """Receive update from address

        Args:
            msg (PeerKV): Update message
            address (bytes): Address of sender
        """
        pk_response = PeerKV()
        key, val = msg.get_push_key_val()

        self.printf(f"Recv Update By Push - key:{key} r:{msg.get_r_identity()}")

        self.endpoints_kv.merge(key, val)
        # self.printf(f"Send Update ACK - key:{key} with r:{msg.get_r_identity()}")

        pk_response.return_push_change(msg.get_r_identity())

        self.receive_query_socket.send_multipart(
            pk_response.compile_with_address(address)
        )

    def __finish_update(self, msg: PeerKV):
        """Finish update sequence

        Args:
            msg (PeerKV): ACK Message
        """
        r = msg.get_r_identity()
        if self.open_messages[f"update-{r}"].is_complete():
            # self.printf(f"Recv ACK on Push Change r:{r} - duplicate")
            return  # don't need to answer. Already received response due to dealer.

        # self.printf(f"Recv ACK on Push Change r:{r}")
        self.open_messages[f"update-{r}"].mark_done()

    # Receiving methods ----------------------- No blocking allowed!

    def send_dummy_command(self, command: bytes, endpoint: str):
        """Send dummy command

        Args:
            command (bytes): Command
            endpoint (str): Endpoint
        """
        msg = BasicMultipartMessage()
        msg.set_val(command)

        self.connected_sockets[endpoint].rsoc.add_message(msg.compile(), 0, 1)

    def __receive_dummy(self, msg: BasicMultipartMessage, address: bytes):
        """Receive dummy command from address

        Args:
            msg (BasicMultipartMessage): Message
            address (bytes): Address of sender
        """
        self.printf(f"Recv dummy command {msg.get_val().decode()}")

    def send_dummy_data(self, data: bytes, endpoint: str):
        """Send dummy data from router

        Args:
            data (bytes): Data
            endpoint (str): Endpoint
        """
        addr = self.inbound_peers[endpoint].addr
        msg = BasicMultipartMessage()
        msg.set_val(data)
        lst = msg.compile_with_address(addr)
        lst.insert(0, b"R-Relay")
        self.control_socket_outside.send_multipart(lst)

    def __receive_dummy_data(self, msg: BasicMultipartMessage):
        """Receive Dummy Data - dealer

        Args:
            msg (BasicMultipartMessage): Message
        """
        self.printf(f"Received dummy data! {msg.get_val().decode('utf-8')}")

        # msg
        # print("Dummy")

        # do nothing.

    def __prune(self, poller: zmq.Poller):
        """Prune all expired connections

        Args:
            poller (zmq.Poller): Poller from serving thread
        """
        # prune
        rms = []
        for endpoint in self.connected_peers:
            if not (self.endpoints_kv.has_or_expired(kv_key(IP_KEY, endpoint))):
                continue  # does not exist, no need to prune (will be added later)
            if self.endpoints_kv.has(kv_key(IP_KEY, endpoint)):
                continue  # is currently active
            # same as remove peer thread
            rms.append(endpoint)

        for endpoint in rms:
            self.printf(f"Peer {endpoint} disconnected (expired)! - Dealer")
            self.connected_peers.remove(endpoint)
            self.connected_sockets[endpoint].rsoc.remove_peer(endpoint)
            while self.connected_sockets[endpoint].rsoc.get_number_peers() != 0:
                pass  # wait until done
            poller.unregister(self.connected_sockets[endpoint].out)
            self.connected_sockets[endpoint].rsoc.stop()
            del self.connected_sockets[endpoint]
            self.new_data = True

    def __prune_inbound(self):
        """Prune all inbound peers from cache

        To be executed from serving thread only
        """
        rms = []
        for endpoint in self.inbound_peers:
            if not (self.endpoints_kv.has_or_expired(kv_key(IP_KEY, endpoint))):
                continue  # does not exist, no need to prune (will be added later)
            if self.endpoints_kv.has(kv_key(IP_KEY, endpoint)):
                continue  # is currently active

            # same as remove peer thread
            self.printf(f"Peer at {endpoint} disconnected (expired)! - Router")
            del self.inbound_peers_addr[self.inbound_peers[endpoint]["addr"]]
            rms.append(endpoint)

        for endpt in rms:
            del self.inbound_peers[endpt]

    def __prune_kv(self):
        """Prune all expired records from library"""
        self.endpoints_kv.prune()

    def __handle_receiving_socket(self, msg: list[bytes]):
        """Handle information incoming on the ROUTER socket

        Args:
            msg (list[bytes]): multipart message

        Raises:
            ValueError: Malformed message
        """
        addr = msg[0]
        data = msg[1:]

        # self.printf("Received on router")
        # dump(msg)
        # self.printf("---")
        if addr not in self.inbound_peers_addr:
            if data[0] == b"Hello!":
                # good. new peer. hello
                pk = PeerKV_Hello()
                pk.import_msg(data)
                self.__receiving_hello(pk, addr)
            else:
                self.printf("New peer did not say hello! Dropping")

        else:

            peer = self.inbound_peers_addr[addr].endpoint
            self.__is_alive(peer, address=addr)

            if data[0] == b"General":
                pk = PeerKV()  # type: ignore
                pk.import_msg(data)
                if pk.is_fetch_state():
                    self.__receive_state_request(pk, addr)
                elif pk.is_requesting_connection():
                    self.__receive_request_for_connection(pk, addr)
                elif pk.is_push_change():
                    self.__receive_update(pk, addr)
                elif pk.is_requesting_disconnection():
                    self.__receive_disconnect_request(pk, addr)
                else:
                    raise ValueError(
                        "Unknown message received from Query Router Socket"
                    )
            elif data[0] == b"dummy":
                pk = BasicMultipartMessage()  # type: ignore
                pk.import_msg(data)
                self.__receive_dummy(pk, addr)
            else:
                raise ValueError("Unknown message received from Query Router Socket")

    def __handle_receiving_dealer_socket(self, msg: list[bytes], peer: str):
        """Handle information coming in from the DEALER socket

        Args:
            msg (list[bytes]): Multipart message
            peer (str): Peer Endpoint

        Raises:
            ValueError: Malformed Message
        """
        # self.printf("Received on dealer")
        # dump(msg)
        # self.printf("---")

        if msg[0] == b"Welcome":
            pk = PeerKV_Hello()
            pk.import_msg(msg)
            self.__finish_hello(pk)

        elif msg[0] == b"General":
            self.__is_alive(peer, dealer=True)
            pk = PeerKV()  # type: ignore
            pk.import_msg(msg)
            if pk.is_return_state():
                self.__finish_state_request(pk)
            elif pk.is_push_change_receive():
                self.__finish_update(pk)
            elif pk.is_requesting_connection_feedback():
                self.__finish_request_for_connection(pk)
            elif pk.is_error_msg():
                error, cmd = pk.get_error_code()
                if error == 10:
                    # Must reconnect to server, I must have dropped or previously connected
                    # resend a hello
                    self.printf(f"Failed command: {cmd}")
                    self.__send_hello(peer)
                    # wait for the RE to then request it again.
            else:
                raise ValueError("Unknown message received from Dealer Socket")

        elif msg[0] == b"dummy":
            self.__is_alive(peer, dealer=True)
            pk = BasicMultipartMessage()  # type: ignore
            pk.import_msg(msg)
            self.__receive_dummy_data(pk)

        else:
            raise ValueError("Unknown message received from Dealer Socket")

    # to be run by a thread!
    def __handle_responses(self, status_socket: zmq.Socket):
        """The thread for the server. Handles all receiving requests on all sockets

        Args:
            status_socket (zmq.Socket): Internal control socket

        """
        poller = zmq.Poller()  # put number in here if you want a timeout
        poller.register(self.receive_query_socket, zmq.POLLIN)
        poller.register(status_socket, zmq.POLLIN)

        while True:
            # tell people I'm alive
            base = kv_key(IDENTITY_KEY, self.my_identity)
            # self.printf(f"{ttl}, {time.time()}, {ttl - time.time()}, {kv_key(IP_KEY,endpoint)}")
            self.set(
                base, f"{self.my_identity} + LIMIT", ttl=IDENTITY_TTL + time.time()
            )

            # wait
            socket_receiving = dict(poller.poll(5000))
            if status_socket in socket_receiving:
                msg = status_socket.recv_multipart()
                if msg[0] == b"STOP":
                    break
                if msg[0] == b"connect":
                    endpt = msg[1].decode("utf-8")
                    poller.register(self.connected_sockets[endpt].out, zmq.POLLIN)
                if msg[0] == b"disconnect":
                    endpt = msg[1].decode("utf-8")
                    poller.unregister(self.connected_sockets[endpt].out)
                if msg[0] == b"R-Relay":
                    dat = msg[1:]
                    self.receive_query_socket.send_multipart(dat)

            if self.receive_query_socket in socket_receiving:
                msg = self.receive_query_socket.recv_multipart()
                self.__handle_receiving_socket(msg)

            for peer in self.connected_sockets:
                socket = self.connected_sockets[peer].out
                if not (socket) in socket_receiving:
                    continue

                socket = cast(zmq.Socket, socket)

                msg = socket.recv_multipart()
                self.__handle_receiving_dealer_socket(msg, peer)

            self.__prune(poller)
            self.__prune_inbound()
            self.__prune_kv()  # must go after the above.
