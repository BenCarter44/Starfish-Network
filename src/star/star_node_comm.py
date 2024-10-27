import asyncio
import queue
import threading
from node_queue_interface import Node_Request, Node_Response
from transport_protocol import *
from DHT import *
import sys

# Manages a node.
# Listen for network requests.
# Dispatch requests.

# Uses one or multiple transport classes. (transports are included in asyncio.)


class Node:
    """Does not ship with async loop integration..."""

    def __init__(self, bin_addr: bytes) -> None:
        """Create a Node Communication Manager Object.

        Uses default asyncio event loop
        """

        self.local_serving_addresses: dict[Star_Address, asyncio.Task] = {}
        self.receiving_queue: asyncio.Queue[Node_Request] = asyncio.Queue()
        self.engine_receiving_queue: queue.Queue[Node_Response] = (
            queue.Queue()
        )  # will be added to from engine thread

        # Transport is defined by the address it is serving.
        self.output_queues: dict[Star_Address, asyncio.Queue[Node_Response]] = {}
        self.bin_addr = bin_addr
        self.task_dht = DHT(self.bin_addr)

        # Temporary hard coded bin addr and IP. Later becomes a DHT
        self.addr_table = {
            b"Address One": Star_Address("tcp", "127.0.0.1", 9280),
            b"Address Two": Star_Address("tcp", "127.0.0.1", 9281),
            b"Address Three": Star_Address("tcp", "127.0.0.1", 9282),
            b"Address Four": Star_Address("tcp", "127.0.0.1", 9283),
        }

        self.task_dht.update_addresses(list(self.addr_table.keys()))
        self.temp_queue_number = 0
        self.temp_queues: dict[int, asyncio.Queue] = {}

    ################################## External API

    async def add_transport(self, tp: Generic_TCP) -> None:
        """Add a transport that can be used for listening and sending messages.

        Args:
            tp (Generic_TCP): Transport Object

        Raises:
            ValueError: Raise error if already added to Node previously.
        """
        if tp.address in self.output_queues:
            raise ValueError("Already added!")
        self.output_queues[tp.address] = asyncio.Queue()
        self.local_serving_addresses[tp.address] = asyncio.create_task(
            tp.initalize_transport(self.receiving_queue, self.output_queues[tp.address])
        )
        if len(self.output_queues) == 1:
            # receive task isn't running!
            asyncio.create_task(self.receive_queue_processor())

    async def allocate_task(self, tp: Generic_TCP, task_id, task_val):
        response = self.task_dht.set(task_id, task_val)
        # send it to peers!
        peers = response.neighbor_addrs
        print("PEERS: ", peers)
        for peer in peers:
            if peer == self.bin_addr:
                continue

            ip_addr = self.addr_table[peer]
            headers_send = {
                "METHOD": "TASK_ALLOCATE",
                "DHT_NODE_IGNORE": [self.bin_addr],
                "DHT_KEY": task_id,
                "FROM": self.bin_addr,
            }
            print(f"Allocating task: [{task_id}]={task_val} - Send to peer {peer}")
            await self.send_to(tp, ip_addr, headers_send, task_val)

    ########################## Queue Handling

    async def receive_queue_processor(self):
        """Receive from transports.

        Analogous to request/response router (app.route)
        """

        while True:
            item: Node_Request = await self.receiving_queue.get()
            method = item.headers["METHOD"]
            is_server = item.routing["SOURCE"] == "SERVER"
            print(f"Receive: {item}")
            continue_num = None
            og: dict = item.routing.get("ORIGINAL")
            if og is not None:
                continue_num = og.get("CONTINUE")
            if continue_num is not None and continue_num in self.temp_queues:
                await self.temp_queues[continue_num].put(item)
                continue  # do not process

            if method == "PING" and is_server:
                asyncio.create_task(self.ping_server(item))

            elif method == "PONG" and not (is_server):  # client
                asyncio.create_task(self.pong_client(item))

            elif method == "TASK_ALLOCATE" and is_server:
                # required, not await as it must keep processing events and not block
                asyncio.create_task(self.task_allocation(item))

            elif method == "TASK_ALLOCATE" and not is_server:
                asyncio.create_task(self.task_allocation_client(item))

            else:
                print(f"Unknown response/request: {method} Is Server: {is_server}")

            # run the event handling here!
            # can do asyncio.create_task() if wanted? Will need a max though.

    async def send_to_transport(
        self, transport: Star_Address, node_response: Node_Response
    ):
        """Send to transport. For servers.

        Analogous to return statement inside route func def
        """
        await self.output_queues[transport].put(node_response)

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
        if tp_addr not in self.output_queues:
            raise ValueError("Transport has not been added to node")

        await self.output_queues[tp_addr].put(connect_request)

    ########################## Processing Requests/Routing Magic.
    # Analogous to the route def func's.
    # Both server and client

    async def ping_server(self, item: Node_Request):
        """PING Server command"""
        print(f"Node: Got PING! {item.body}")
        routing = {"SYSTEM": "FEEDBACK", "ORIGINAL": item.routing}
        headers = {"METHOD": "PONG"}
        num = item.routing["TP_ID"]
        data = f"Server Port {num} Response to '{item.body}'!"
        out = Node_Response(routing=routing, headers=headers, body=data)
        await self.send_to_transport(item.routing["TP_ID"], out)

    async def pong_client(self, item: Node_Request):
        """PONG Client command"""
        print(f"Node: Got PONG! {item.body}")

    # Task Allocation Server/Client flow - set - DHT recursive
    # Task DNS Server/Client flow - get - DHT recursive
    # Sending events (for tasks)

    # Peer Routing Commands:
    # Peer Discovery: Who do I know? (Simply returns peer list)
    # Peer Dial Allocation - set - DHT recursive
    # Peer Dial DNS - get - DHT recursive

    async def task_allocation(self, item: Node_Request):
        # Request node to allocate task.
        headers = item.headers
        body = item.body

        ignore_nodes = headers["DHT_NODE_IGNORE"]
        key = headers["DHT_KEY"]
        from_bin_addr = headers["FROM"]

        print(
            f"{self.bin_addr} Received Task Allocation Request from {from_bin_addr}: [{key}]={body}"
        )

        ignore_nodes.append(self.bin_addr)

        res = self.task_dht.set(key, body)
        print(f"DHT returned: {res.response_code}")
        if res.response_code == "NEIGHBOR_UPDATE_CACHE":
            send_outs = []
            for neighbor in res.neighbor_addrs:
                if neighbor not in ignore_nodes:
                    send_outs.append(neighbor)
            if len(send_outs) == 0:
                # no neighbors to send to!
                routing = {"SYSTEM": "FEEDBACK", "ORIGINAL": item.routing}
                headers = {
                    "METHOD": "TASK_ALLOCATE",
                    "CODE": "NO_ROUTES_AVAILABLE",
                    "CHAIN": ignore_nodes,
                }
                print(f"Sending NO ROUTE AVAILABLE (direct) for [{key}]={body}")
                out = Node_Response(routing=routing, headers=headers, body=None)
                await self.send_to_transport(item.routing["TP_ID"], out)
                return

            # It is not to be owned by server. So, send request to peers
            # use onion method, meaning server makes request on behalf of client
            found = False
            found_addrs = []

            print("SEND_OUTS: ", send_outs)

            for addr in send_outs:
                # TODO: Only sends to one person. Because, if multiple, which person's response should send back to the host?
                headers_send = {
                    "METHOD": "TASK_ALLOCATE",
                    "DHT_NODE_IGNORE": ignore_nodes,
                    "DHT_KEY": key,
                    "FROM": self.bin_addr,
                }
                continue_id = self.temp_queue_number

                self.temp_queue_number += 1
                routing = {"CONTINUE": continue_id}

                self.temp_queues[continue_id] = asyncio.Queue()

                ip_addr = self.addr_table[addr]
                print(
                    f"Hash Miss! [{key}]={body} - {self.bin_addr} Send to peer {addr}"
                )
                await self.send_to(
                    item.routing["TP_ID"],
                    ip_addr,
                    headers_send,
                    body,
                    routing_custom=routing,
                )
                response: Node_Request = await self.temp_queues[continue_id].get()
                if response.headers.get("CODE") == "SUCCESS_OWNED":
                    print(f"Child return success [{key}]={body}")
                    found = True
                    found_addrs.append(addr)
                del self.temp_queues[continue_id]  # no longer needed!

            if not (found):
                # no neighbors to send to!
                routing = {"SYSTEM": "FEEDBACK", "ORIGINAL": item.routing}
                headers = {
                    "METHOD": "TASK_ALLOCATE",
                    "CODE": "NO_ROUTES_AVAILABLE",
                    "CHAIN": ignore_nodes,
                }
                print(f"Sending NO ROUTE AVAILABLE (indirect) for [{key}]={body}")
                out = Node_Response(routing=routing, headers=headers, body=None)
                await self.send_to_transport(item.routing["TP_ID"], out)
                return

            routing = {"SYSTEM": "FEEDBACK", "ORIGINAL": item.routing}
            headers = {
                "METHOD": "TASK_ALLOCATE",
                "CODE": "SUCCESS_OWNED_BY_CHILD",
                "CHAIN": ignore_nodes,
                "OWNED": found_addrs,
            }
            print(f"Sending SUCCESS OWNED BY CHILD for [{key}]={body}")
            out = Node_Response(routing=routing, headers=headers, body=None)
            await self.send_to_transport(item.routing["TP_ID"], out)
            return

        else:
            # Node owns it now!
            routing = {"SYSTEM": "FEEDBACK", "ORIGINAL": item.routing}
            headers = {
                "METHOD": "TASK_ALLOCATE",
                "CODE": "SUCCESS_OWNED",
                "CHAIN": ignore_nodes,
            }
            print(f"Sending DIRECT OWNED for [{key}]={body}")
            out = Node_Response(routing=routing, headers=headers, body=None)
            await self.send_to_transport(item.routing["TP_ID"], out)
            return

    async def task_allocation_client(self, item: Node_Request):
        # Receiving data from server side.
        code_return = item.headers.get("CODE")
        print(f"Got Server Response for task allocation: CODE: {code_return}")
        if code_return == "NO_ROUTES_AVAILABLE":
            chain = item.headers.get("CHAIN")
            print(
                f"No routes available. Currently however stored here in cache: {chain}"
            )
            return
        if code_return == "SUCCESS_OWNED_BY_CHILD":
            found_addrs = item.headers.get("OWNED")
            print(f"\nChild(ren) is/are holding the keys!!!!!!!!!! {found_addrs}\n")
            return
        if code_return == "SUCCESS_OWNED":
            print("Direct peer owns the key. ")
            return

        print(f"Malformed data received by client: {item}")


if __name__ == "__main__":

    async def monitor():
        """Get a count of how many tasks scheduled on the asyncio loop."""
        while True:
            await asyncio.sleep(1)
            print("Tasks currently running: ", len(asyncio.all_tasks()))

    async def main():
        mode = sys.argv[1]
        serve_first_two = int(mode)
        print("SERVE: ", serve_first_two)

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

        client_addr = addr_table[b"Address One"]
        client_addr2 = addr_table[b"Address Two"]
        client_addr3 = addr_table[b"Address Three"]
        client_addr4 = addr_table[b"Address Four"]

        if serve_first_two:
            node_1 = Node(b"Address One")
            node_2 = Node(b"Address Two")
        else:
            node_1 = Node(b"Address Three")
            node_2 = Node(b"Address Four")

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

        for x in range(1, 100):
            name = await asyncio.to_thread(input, "Wait......  1 \n")

            await node_1.allocate_task(tcp_ip_interface1, f"Test ID {x}", "Test Val")

            name = await asyncio.to_thread(input, "Wait......  2 \n")

            await node_2.allocate_task(tcp_ip_interface2, f"Test ID2 {x}", "Test Val")

        await asyncio.sleep(1000)

    asyncio.run(main())
