import asyncio
import queue
import string
import threading
from node_queue_interface import Node_Request, Node_Response
from transport_protocol import *
from DHT import *
from star_engine import NodeEngine
import star_components as star
import sys
import logging
import uuid
import zmq.asyncio
import os

logger = logging.getLogger(__name__)

# Manages a node.
# Listen for network requests.
# Dispatch requests.

# Uses one or multiple transport classes. (transports are included in asyncio.)


class Node:
    """Does not ship with async loop integration..."""

    def __init__(self, bin_addr: bytes, user_id: bytes) -> None:
        """Create a Node Communication Manager Object.

        Uses default asyncio event loop
        """

        self.engine = NodeEngine(bin_addr)
        star.BINDINGS = self.engine.return_component_bindings()
        self.engine.send_event_handler = self.send_event
        self.user_id = user_id
        self.local_serving_addresses: dict[Star_Address, asyncio.Task] = {}
        self.added_transports: dict[Star_Address, bytes] = {}
        self.added_transports_rev: dict[bytes, Star_Address] = {}

        self.ctx = zmq.asyncio.Context()
        self.transport_socket = self.ctx.socket(zmq.ROUTER)
        self.iface = "inproc://%s" % binascii.hexlify(os.urandom(8)).decode("utf-8")
        self.transport_socket.bind(self.iface)

        self.internal_feedback_counter = 0
        self.internal_feedback: dict[int, asyncio.Queue] = {}  # has event triggering.
        # Transport is defined by the address it is serving.
        self.bin_addr = bin_addr

        # task DHT
        self.task_dht = DHT(self.bin_addr)

        # peer routing.
        self.peer_dht = DHT(self.bin_addr)  # [peerID] = TTL[Star_Address]

        # peer discovery
        # net bootstrap:
        #     fetch known peers from friend (one you connect to)
        # peer on network:
        #     net search (look up random address.... keep track of the jumps.)

        # Need the following queries:
        #   Peer DHT get.  <-- make a generalized distributed handler
        #   Peer DHT set. <-- make a generalized distributed handler
        #   Get known peers.  <-- this is the main one.

        # Temporary hard coded bin addr and IP. Later becomes a DHT
        self.addr_table = {
            b"Address One": Star_Address("tcp", "127.0.0.1", 9280),
            b"Address Two": Star_Address("tcp", "127.0.0.1", 9281),
            # b"Address Three": Star_Address("tcp", "127.0.0.1", 9282),
            # b"Address Four": Star_Address("tcp", "127.0.0.1", 9283),
        }

        self.task_dht.update_addresses(list(self.addr_table.keys()))
        self.default_tp: Generic_TCP = None  # type: ignore

    ################################ Engine Interface

    async def start_engine(self):
        asyncio.create_task(self.receive_queue_processor())
        asyncio.create_task(self.engine.start_loops())

    async def start_program(self, program: star.Program, tp: Generic_TCP):
        task_list: set[star.StarTask] = program.task_list
        if task_list is None:
            raise ValueError("No tasks in program!")
        if program.start is None:
            raise ValueError("No event to start the program!")

        # create a process. Create a random UUID for the process. It can't conflict
        # with already running processes for the user.
        proc = star.StarProcess(
            self.user_id,
            uuid.uuid4().bytes,
        )
        for task in task_list:
            proc.add_task(task)

        for task in proc.get_tasks():
            assert isinstance(task, star.StarTask)
            await self.allocate_task(tp, task)  # includes callable inside.

        program.start.target.attach_to_process(proc)
        await self.send_event(program.start)
        self.clear_cache()  # for now, to force the distributed nature.
        return proc

    async def engine_allocate(self, task: star.StarTask):
        # key is TaskIdentifier
        # body is (func,bool)
        logger.info(f"Task {task} Allocated! on {self.bin_addr!r}")
        self.engine.import_task(task)

    async def send_event(self, evt: star.Event):
        ti = evt.target
        if ti.user_id == star.ZERO_32 or ti.process_id == star.ZERO_32:
            logger.warning("Dropping event. User/Process 0!")
            logger.warning(ti)
            return
        logger.info(f"Send EVT target: {evt.data} {evt.target}")
        storage_address = await self.search_task(self.default_tp, ti)
        if storage_address is None:
            logger.warning("EVT NOT FOUND!")
            return

        ip_addr = self.addr_table[storage_address]

        headers_send = {
            "METHOD": "EVENT",
            "TASK_IDENTIFIER": ti,
            "FROM": self.bin_addr,
        }
        logger.debug(
            f"Sending event {evt.target!r} to {storage_address!r} from {self.bin_addr!r}"
        )
        await self.send_to(self.default_tp, ip_addr, headers_send, evt)

    ################################## External API

    def clear_cache(self):
        self.task_dht.clear_cache()

    async def add_transport(self, tp: Generic_TCP) -> None:
        """Add a transport that can be used for listening and sending messages.

        Args:
            tp (Generic_TCP): Transport Object

        Raises:
            ValueError: Raise error if already added to Node previously.
        """
        if tp.address in self.added_transports:
            raise ValueError("Already added!")
        r = os.urandom(8)
        self.added_transports[tp.address] = r
        self.added_transports_rev[r] = tp.address
        await tp.attach(
            self.iface, r, self.ctx
        )  # possible deadlock.... check. Wait for attach when await for receive.
        self.default_tp = tp

    async def allocate_task(self, tp: Generic_TCP, task: star.StarTask):
        assert isinstance(task, star.StarTask)
        response = self.task_dht.set(
            task,
            self.bin_addr,
            post_to_cache=False,
            hash_func_in=star.task_hash,
        )  # address of host. Don't actually store it. (except if owned!)
        # send it to peers!

        if response.response_code == "NEIGHBOR_UPDATE_AND_OWN":
            await self.engine_allocate(task)

        peers = response.neighbor_addrs
        # logger.debug("PEERS: ", peers)
        for peer in peers:
            if peer == self.bin_addr:
                continue

            ip_addr = self.addr_table[peer]
            headers_send = {
                "METHOD": "DHT_STORE",
                "DHT_SELECT": "TASK",
                "DHT_NODE_IGNORE": [self.bin_addr],
                "DHT_KEY": task,
                "FROM": self.bin_addr,
            }
            logger.info(f"Allocating task: {task} - Send to peer {peer!r}")
            await self.send_to(tp, ip_addr, headers_send, task)
            await asyncio.sleep(0)

    async def search_task(
        self, tp: Generic_TCP, task_id: star.StarTask
    ):  ## GET DHT ITEM.
        logger.debug(f"Search For Task: {task_id}")
        return await self.search_dht(tp, task_id, "TASK")

    async def search_dht(self, tp: Generic_TCP, key, dht_select: str):
        resp = self.retrieve_task(key)

        if resp.response_code == "SELF_FOUND":
            logger.debug(f"Search For {key} - Found Local! {self.bin_addr!r}")
            return resp.data

        # Not stored in local DHT. Look up nodes closer.
        for addr in resp.neighbor_addrs:
            if addr == self.bin_addr:
                continue
            headers = {
                "METHOD": "DHT_FETCH",
                "DHT_SELECT": dht_select,
                "DHT_NODE_IGNORE": [self.bin_addr],
                "DHT_KEY": key,
                "FROM": self.bin_addr,
            }

            ip_addr = self.addr_table[addr]
            continue_id = self.internal_feedback_counter
            self.internal_feedback_counter += 1

            self.internal_feedback[continue_id] = (
                asyncio.Queue()
            )  # has event triggering. That is all the queue is used for.

            routing = {"CONTINUE": continue_id}

            logger.debug(f"Search For {key} - send_to")
            await self.send_to(tp, ip_addr, headers, None, routing_custom=routing)

            logger.debug(f"Search For {key} - q wait")
            response: Node_Request = await self.internal_feedback[continue_id].get()
            del self.internal_feedback[continue_id]

            code = response.headers["CODE"]
            if code == "FOUND":
                chain = response.headers["CHAIN"]
                logger.debug(f"Search For: {key} - Found Remote! {chain[-1]}")
                if dht_select == "TASK":
                    resp = self.store_task(key, response.body, cached=True)
                elif dht_select == "PEER":
                    pass
                    # resp = self.store_peer(key, response.body, cached=True)
                return response.body

        # not found!
        logger.debug(f"Search For: {key} - Not Found!")
        return None

    ########################## Queue Handling

    async def receive_queue_processor(self):
        """Receive from transports.

        Analogous to request/response router (app.route)
        """

        while True:
            logger.debug("Waiting for item in comm")
            # FORMAT:
            # 0: ROUTER ADDRESS
            # 1: bytes: STOP/OK/FEEDBACK
            # 2: routing dill
            # 3: header dill
            # 4: body dill
            raw_in = await self.transport_socket.recv_multipart()
            logger.debug("Got receipt from TP")
            transport_addr = raw_in[0]
            if transport_addr not in self.added_transports_rev:
                logger.warning("Got unknown connection on recv q")
                is_server = item.routing["SOURCE"] == "SERVER"
                if is_server:
                    asyncio.create_task(self.error_server(item))
                continue
            item = Node_Request.extract_multipart(raw_in[2:])
            logger.debug(item)
            method = item.headers["METHOD"]
            is_server = item.routing["SOURCE"] == "SERVER"
            continue_num = None
            og: dict = item.routing.get("ORIGINAL")
            if og is not None:
                continue_num = og.get("CONTINUE")
            if continue_num is not None:
                await self.internal_feedback[continue_num].put(item)
                is_server = item.routing["SOURCE"] == "SERVER"
                if is_server:
                    asyncio.create_task(self.error_server(item))
                continue  # do not process

            if method == "PING" and is_server:
                asyncio.create_task(self.ping_server(item))

            elif method == "PONG" and not (is_server):  # client
                asyncio.create_task(self.pong_client(item))

            elif method == "DHT_FETCH" and is_server:
                asyncio.create_task(self.dht_search(item))

            elif method == "DHT_STORE" and is_server:
                asyncio.create_task(self.dht_store(item))

            elif method == "DHT_STORE" and not is_server:
                # required, not await as it must keep processing events and not block
                asyncio.create_task(self.dht_store_client(item))

            elif method == "EVENT" and is_server:
                asyncio.create_task(self.process_event(item))

            else:
                logger.warning(
                    f"Unknown response/request: {method} Is Server: {is_server}"
                )

            # run the event handling here!
            # can do asyncio.create_task() if wanted? Will need a max though.

    async def send_to_transport(
        self, transport: Star_Address, node_response: Node_Response
    ):
        """Send to transport. For servers.

        Analogous to return statement inside route func def
        """
        transport_id = self.added_transports[transport]
        # FORMAT:
        # (0): ROUTER ADDR
        # 0: bytes: STOP/OK/FEEDBACK
        # 1: routing dill
        # 2: header dill
        # 3: body dill
        await self.transport_socket.send_multipart(
            [transport_id, b"OK"] + node_response.get_multipart()
        )
        # [transport].put(node_response)

    async def send_to(
        self,
        tp: Generic_TCP | Star_Address,
        address: Star_Address,
        headers,
        body,
        routing_custom={},
    ):
        """Send using transport. For clients

        Analogous to urllib.open()"""

        routing = {
            "SYSTEM": "CONNECT",
            "DEST": address,
        }
        routing = routing | routing_custom

        if isinstance(tp, Generic_TCP):
            tp_addr = tp.address
        elif isinstance(tp, Star_Address):
            tp_addr = tp

        # It's a "RESPONSE" as it is being sent out from node_comm.
        connect_request = Node_Response(routing=routing, headers=headers, body=body)
        if tp_addr not in self.added_transports:
            raise ValueError("Transport has not been added to node")

        transport_id = self.added_transports[tp_addr]
        # FORMAT:
        # (0): ROUTER ADDR
        # 0: bytes: STOP/OK/FEEDBACK
        # 1: routing dill
        # 2: header dill
        # 3: body dill
        await self.transport_socket.send_multipart(
            [transport_id, b"OK"] + connect_request.get_multipart()
        )
        # await asyncio.sleep(60)

    ########################## Processing Requests/Routing Magic.
    # Analogous to the route def func's.
    # Both server and client

    async def ping_server(self, item: Node_Request):
        """PING Server command"""
        logger.info(f"Node: Got PING! {item.body}")
        routing = {"SYSTEM": "FEEDBACK", "ORIGINAL": item.routing}
        headers = {"METHOD": "PONG"}
        num = item.routing["TP_ID"]
        data = f"Server Port {num} Response to '{item.body}'!"
        out = Node_Response(routing=routing, headers=headers, body=data)
        await self.send_to_transport(item.routing["TP_ID"], out)

    async def error_server(self, item: Node_Request):
        """PING Server command"""
        logger.info(f"Node: Got PING! {item.body}")
        routing = {"SYSTEM": "FEEDBACK", "ORIGINAL": item.routing}
        headers = {"METHOD": "NA"}
        num = item.routing["TP_ID"]
        data = f"Incorrect/unknown command"
        out = Node_Response(routing=routing, headers=headers, body=data)
        await self.send_to_transport(item.routing["TP_ID"], out)

    async def pong_client(self, item: Node_Request):
        """PONG Client command"""
        logger.info(f"Node: Got PONG! {item.body}")

    # Task Allocation Server/Client flow - set - DHT recursive
    # Task DNS Server/Client flow - get - DHT recursive
    # Sending events (for tasks)

    # Peer Routing Commands:
    # Peer Discovery: Who do I know? (Simply returns peer list)
    # Peer Dial Allocation - set - DHT recursive
    # Peer Dial DNS - get - DHT recursive

    async def process_event(self, item: Node_Request):
        headers = item.headers
        logger.debug(f"{self.bin_addr!r} Got EVENT from {headers['FROM']}")
        ti = headers["TASK_IDENTIFIER"]

        evt = item.body

        self.engine.recv_event(evt)
        routing = {"SYSTEM": "FEEDBACK", "ORIGINAL": item.routing}
        resp = Node_Response(routing=routing, headers={"METHOD": "CLOSE"}, body=None)
        await self.send_to_transport(item.routing["TP_ID"], resp)

    def retrieve_task(self, key: star.StarTask):
        resp = self.task_dht.get(key, hash_func_in=star.task_hash)
        return resp

    def store_task(self, key, body, cached=False):
        if cached:
            resp = self.task_dht.set_cache(key, body)
        else:
            # resp = self.task_dht.set(key, body, hash_func_in=star.task_hash)
            resp = self.task_dht.set(
                key, body, post_to_cache=False
            )  # don't actually store the body, store address.
        return resp

    ############################ DHT METHODS

    async def dht_store_client(self, item: Node_Request):  # DHT Set
        # Receiving data from server side.
        code_return = item.headers.get("CODE")
        logger.debug(f"Got Server Response for task allocation: CODE: {code_return}")
        if code_return == "NO_ROUTES_AVAILABLE":
            chain = item.headers.get("CHAIN")
            logger.debug(
                f"No routes available. Currently however stored here in cache: {chain}"
            )
            return
        if code_return == "SUCCESS_OWNED_BY_CHILD":
            found_addrs = item.headers.get("OWNED")
            logger.debug(
                f"\nChild(ren) is/are holding the keys!!!!!!!!!! {found_addrs}\n"
            )
            return
        if code_return == "SUCCESS_OWNED":
            logger.debug("Direct peer owns the key. ")
            return

        logger.warning(f"Malformed data received by client: {item}")

    async def dht_store(self, item: Node_Request):  # server
        # Request node to allocate task.
        headers = item.headers
        body = item.body

        dht_select = headers["DHT_SELECT"]
        ignore_nodes = headers["DHT_NODE_IGNORE"]
        key = headers["DHT_KEY"]
        from_bin_addr = headers["FROM"]

        logger.debug(
            f"{self.bin_addr!r} Received Task Allocation Request from {from_bin_addr!r}: [{key}]={body}"
        )

        ignore_nodes.append(self.bin_addr)

        if dht_select == "TASK":
            res = self.store_task(key, self.bin_addr, False)

        logger.debug(f"DHT returned: {res.response_code}")
        if res.response_code == "NEIGHBOR_UPDATE_CACHE":
            send_outs = []
            for neighbor in res.neighbor_addrs:
                if neighbor not in ignore_nodes:
                    send_outs.append(neighbor)
            if len(send_outs) == 0:
                # no neighbors to send to!
                routing = {"SYSTEM": "FEEDBACK", "ORIGINAL": item.routing}
                headers = {
                    "METHOD": "DHT_STORE",
                    "DHT_SELECT": dht_select,
                    "CODE": "NO_ROUTES_AVAILABLE",
                    "CHAIN": ignore_nodes,
                }
                logger.debug(f"Sending NO ROUTE AVAILABLE (direct) for [{key}]={body}")
                out = Node_Response(routing=routing, headers=headers, body=None)
                await self.send_to_transport(item.routing["TP_ID"], out)
                return

            # It is not to be owned by server. So, send request to peers
            # use onion method, meaning server makes request on behalf of client
            found = False
            found_addrs = []

            for addr in send_outs:
                # TODO: Only sends to one person. Because, if multiple, which person's response should send back to the host?
                headers_send = {
                    "METHOD": "DHT_STORE",
                    "DHT_SELECT": dht_select,
                    "DHT_NODE_IGNORE": ignore_nodes,
                    "DHT_KEY": key,
                    "FROM": self.bin_addr,
                }
                continue_id = self.internal_feedback_counter

                self.internal_feedback_counter += 1
                routing = {"CONTINUE": continue_id}  # type: ignore

                self.internal_feedback[continue_id] = asyncio.Queue()

                ip_addr = self.addr_table[addr]
                logger.debug(
                    f"Hash Miss! [{key}]={body} - {self.bin_addr!r} Send to peer {addr!r}"
                )
                await self.send_to(
                    item.routing["TP_ID"],
                    ip_addr,
                    headers_send,
                    body,
                    routing_custom=routing,
                )
                response: Node_Request = await self.internal_feedback[continue_id].get()
                if response.headers.get("CODE") == "SUCCESS_OWNED":
                    logger.debug(f"Child return success [{key}]={body}")
                    found = True
                    found_addrs.append(addr)
                del self.internal_feedback[continue_id]  # no longer needed!

            if not (found):
                # no neighbors to send to!
                routing = {"SYSTEM": "FEEDBACK", "ORIGINAL": item.routing}
                headers = {
                    "METHOD": "DHT_STORE",
                    "DHT_SELECT": dht_select,
                    "CODE": "NO_ROUTES_AVAILABLE",
                    "CHAIN": ignore_nodes,
                }
                logger.debug(
                    f"Sending NO ROUTE AVAILABLE (indirect) for [{key}]={body}"
                )
                out = Node_Response(routing=routing, headers=headers, body=None)
                await self.send_to_transport(item.routing["TP_ID"], out)
                return

            routing = {"SYSTEM": "FEEDBACK", "ORIGINAL": item.routing}
            headers = {
                "METHOD": "DHT_STORE",
                "DHT_SELECT": dht_select,
                "CODE": "SUCCESS_OWNED_BY_CHILD",
                "CHAIN": ignore_nodes,
                "OWNED": found_addrs,
            }
            logger.debug(f"Sending SUCCESS OWNED BY CHILD for [{key}]={body}")
            out = Node_Response(routing=routing, headers=headers, body=None)
            await self.send_to_transport(item.routing["TP_ID"], out)
            return

        else:
            # Node owns it now!
            if dht_select == "TASK":
                await self.engine_allocate(key)

            routing = {"SYSTEM": "FEEDBACK", "ORIGINAL": item.routing}
            headers = {
                "METHOD": "DHT_STORE",
                "DHT_SELECT": dht_select,
                "CODE": "SUCCESS_OWNED",
                "CHAIN": ignore_nodes,
            }
            logger.debug(f"Sending DIRECT OWNED for [{key}]={body}")
            out = Node_Response(routing=routing, headers=headers, body=None)
            await self.send_to_transport(item.routing["TP_ID"], out)
            return

    async def dht_search(self, item: Node_Request):
        # Server
        headers = item.headers
        body = item.body

        dht_select = headers["DHT_SELECT"]
        ignore_nodes = headers["DHT_NODE_IGNORE"]
        key = headers["DHT_KEY"]
        from_addr = headers["FROM"]
        ignore_nodes.append(self.bin_addr)

        logger.debug(
            f"{self.bin_addr!r} Received DHT Query for [{key}] from {from_addr}"
        )

        # See if I have it, if not, get something closer

        if dht_select == "TASK":
            resp = self.retrieve_task(cast(star.StarTask, key))

        elif dht_select == "PEER":
            pass
            # resp = self.retrieve_peer(key)

        if resp.response_code == "SELF_FOUND":
            # found!
            logger.debug(f"Found key [{key}] - local server")
            headers_response = {
                "METHOD": "DHT_FETCH",
                "DHT_SELECT": dht_select,
                "CODE": "FOUND",
                "DHT_KEY": key,
                "CHAIN": ignore_nodes,
            }
            routing = {"SYSTEM": "FEEDBACK", "ORIGINAL": item.routing}
            body_response = resp.data
            out = Node_Response(
                routing=routing, headers=headers_response, body=body_response
            )
            await self.send_to_transport(item.routing["TP_ID"], out)
            return

        # Not found! Ask peers.
        for addr in resp.neighbor_addrs:
            if addr in ignore_nodes:
                continue
            headers_new = {
                "METHOD": "DHT_FETCH",
                "DHT_SELECT": dht_select,
                "DHT_NODE_IGNORE": ignore_nodes,
                "DHT_KEY": key,
                "FROM": self.bin_addr,
            }

            ip_addr = self.addr_table[addr]
            continue_id = self.internal_feedback_counter
            self.internal_feedback_counter += 1

            self.internal_feedback[continue_id] = asyncio.Queue()

            routing = {"CONTINUE": continue_id}  # type: ignore
            logger.debug(
                f"Sending request for task DNS - server - {self.bin_addr!r} to {addr!r} for [{key}]"
            )
            await self.send_to(
                item.routing["TP_ID"],
                ip_addr,
                headers_new,
                None,
                routing_custom=routing,
            )
            response: Node_Request = await self.internal_feedback[continue_id].get()
            del self.internal_feedback[continue_id]

            code = response.headers["CODE"]
            if code == "FOUND":
                chain = response.headers["CHAIN"]
                logger.debug(f"Found key [{key}] - remote server {chain[-1]}")
                if dht_select == "TASK":
                    self.store_task(key, response.body, cached=True)
                elif dht_select == "PEER":
                    pass
                    # self.store_peer(key, response.body, cached=True)
                headers_response = {
                    "METHOD": "DHT_FETCH",
                    "DHT_SELECT": dht_select,
                    "CODE": "FOUND",
                    "DHT_KEY": key,
                    "CHAIN": chain,
                }
                routing = {"SYSTEM": "FEEDBACK", "ORIGINAL": item.routing}
                body_response = response.body  # relay back.
                out = Node_Response(
                    routing=routing, headers=headers_response, body=response.body
                )
                await self.send_to_transport(item.routing["TP_ID"], out)
                return

        logger.debug(f"Not Found key [{key}] - local server")
        headers_response = {
            "METHOD": "DHT_FETCH",
            "DHT_SELECT": dht_select,
            "CODE": "NOT_FOUND",
            "DHT_KEY": key,
            "CHAIN": ignore_nodes,
        }
        routing = {"SYSTEM": "FEEDBACK", "ORIGINAL": item.routing}
        body_response = resp.data
        out = Node_Response(routing=routing, headers=headers_response, body=None)
        await self.send_to_transport(item.routing["TP_ID"], out)
        return


if __name__ == "__main__":

    class CustomFormatter(logging.Formatter):
        grey_dark = "\x1b[38;5;7m"
        grey = "\x1b[38;5;123m"
        yellow = "\x1b[33;20m"
        red = "\x1b[31;20m"
        bold_red = "\x1b[1m\x1b[38;5;9m"
        reset = "\x1b[0m"
        format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s (%(filename)s:%(lineno)d)"  # type: ignore

        FORMATS = {
            logging.DEBUG: grey_dark + format + reset,  # type: ignore
            logging.INFO: grey + format + reset,  # type: ignore
            logging.WARNING: yellow + format + reset,  # type: ignore
            logging.ERROR: red + format + reset,  # type: ignore
            logging.CRITICAL: bold_red + format + reset,  # type: ignore
        }

        def format(self, record):  # type: ignore
            log_fmt = self.FORMATS.get(record.levelno)
            formatter = logging.Formatter(log_fmt)
            return formatter.format(record)

    async def monitor():
        """Get a count of how many tasks scheduled on the asyncio loop."""
        while True:
            await asyncio.sleep(1)
            logger.debug("Tasks currently running: ", len(asyncio.all_tasks()))

    async def main():
        # asyncio.create_task(monitor())
        mode = sys.argv[1]
        serve_first_two = int(mode)
        logger.info(f"SERVE: {serve_first_two}")

        """Main function for testing."""
        # asyncio.create_task(monitor())
        addr_table = {
            b"Address One": Star_Address("tcp", "127.0.0.1", 9280),
            b"Address Two": Star_Address("tcp", "127.0.0.1", 9281),
            b"Address Three": Star_Address("tcp", "127.0.0.1", 9282),
            b"Address Four": Star_Address("tcp", "127.0.0.1", 9283),
        }
        serve_addr = addr_table[b"Address One"]
        serve_addr2 = addr_table[b"Address Two"]
        serve_addr3 = addr_table[b"Address Three"]
        serve_addr4 = addr_table[b"Address Four"]

        if serve_first_two:
            node_1 = Node(b"Address One", b"USER ONE")
            node_2 = Node(b"Address Two", b"USER ONE")
            logger.debug("Pizza")
            await node_1.start_engine()
            await node_2.start_engine()
        else:
            node_1 = Node(b"Address Three", b"USER TWO")
            node_2 = Node(b"Address Four", b"USER TWO")
            await node_1.start_engine()
            await node_2.start_engine()

        if serve_first_two:
            tcp_ip_interface1 = Generic_TCP(serve_addr)
            tcp_ip_interface2 = Generic_TCP(serve_addr2)
            await node_1.add_transport(tcp_ip_interface1)
            await node_2.add_transport(tcp_ip_interface2)
        else:
            tcp_ip_interface1 = Generic_TCP(serve_addr3)
            tcp_ip_interface2 = Generic_TCP(serve_addr4)
            await node_1.add_transport(tcp_ip_interface1)
            await node_2.add_transport(tcp_ip_interface2)

        await asyncio.sleep(5)

        if serve_first_two:
            pgrm = star.Program(read_pgrm="my_list_program.star")
            logger.info(
                f"I: Opening program '{pgrm.saved_data['pgrm_name']}' from {pgrm.saved_data['date_compiled']}\n"
            )
            process = await node_1.start_program(pgrm, tcp_ip_interface1)

        else:
            await asyncio.sleep(10)
            # pgrm = star.Program(read_pgrm="file_program.star")
            # logger.info(
            #     f"I: Opening program '{pgrm.saved_data['pgrm_name']}' from {pgrm.saved_data['date_compiled']}\n"
            # )
            # process = await node_1.start_program(pgrm, tcp_ip_interface1)

        # for x in range(1, 100):
        #     name = await asyncio.to_thread(input, "Wait......  1 \n")

        #     await node_1.allocate_task(tcp_ip_interface1, f"Test ID {x}", "Test Val")
        #     name = await asyncio.to_thread(input, "Wait......  2 \n")

        #     await node_2.allocate_task(tcp_ip_interface2, f"Test ID2 {x}", "Test Val")
        #     name = await asyncio.to_thread(input, "Search......  2 \n")
        #     reply = await node_1.search_task(tcp_ip_interface1, f"Test ID2 {x}")
        #     logger.info(f"FINAL REPLY: {reply}")

        await asyncio.sleep(1000)
        logger.critical("Main done!")

    logger = logging.getLogger(__name__)

    # # create console handler with a higher log level
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.DEBUG)
    ch.setFormatter(CustomFormatter())
    logging.basicConfig(handlers=[ch], level=logging.DEBUG)

    asyncio.get_event_loop().set_debug(False)
    asyncio.run(main())
