import asyncio
import queue
import threading
from node_queue_interface import Node_Request, Node_Response
from transport_protocol import *

# Manages a node.
# Listen for network requests.
# Dispatch requests.

# Uses one or multiple transport classes. (transports are included in asyncio.)


class Node:
    """Does not ship with async loop integration..."""

    def __init__(self) -> None:
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

    ########################## Queue Handling

    async def receive_queue_processor(self):
        """Receive from transports.

        Analogous to request/response router (app.route)
        """

        while True:
            item: Node_Request = await self.receiving_queue.get()

            method = item.headers["METHOD"]
            is_server = item.routing["SOURCE"] == "SERVER"

            if method == "PING" and is_server:
                await self.ping_server(item)

            elif method == "PONG" and not (is_server):  # client
                await self.pong_client(item)

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

    async def send_to(self, tp: Generic_TCP, address: Star_Address, headers, body):
        """Send using transport. For clients

        Analogous to urllib.open()"""

        routing = {
            "SYSTEM": "CONNECT",
            "DEST": address,
        }
        # It's a "RESPONSE" as it is being sent out from node_comm.
        connect_request = Node_Response(routing=routing, headers=headers, body=body)
        await self.output_queues[tp.address].put(connect_request)

    ########################## Processing Requests/Routing Magic.
    # Analogous to the route def func's.
    # Both server and client

    async def ping_server(self, item: Node_Response):
        """PING Server command"""
        print(f"Node: Got PING! {item.body}")
        routing = {"SYSTEM": "FEEDBACK", "ORIGINAL": item.routing}
        headers = {"METHOD": "PONG"}
        num = item.routing["TP_ID"]
        data = f"Server Port {num} Response to '{item.body}'!"
        out = Node_Response(routing=routing, headers=headers, body=data)
        await self.send_to_transport(item.routing["TP_ID"], out)

    async def pong_client(self, item: Node_Response):
        """PONG Client command"""
        print(f"Node: Got PONG! {item.body}")

    # Task Allocation Server/Client flow - set - DHT recursive
    # Task DNS Server/Client flow - get - DHT recursive
    # Sending events (for tasks)

    # Peer Routing Commands:
    # Peer Discovery: Who do I know? (Simply returns peer list)
    # Peer Dial Allocation - set - DHT recursive
    # Peer Dial DNS - get - DHT recursive

    # use onion method, meaning server makes request on behalf of client

    # Need DHT Class for storage. Generic DHT class.


if __name__ == "__main__":

    async def monitor():
        """Get a count of how many tasks scheduled on the asyncio loop."""
        while True:
            await asyncio.sleep(1)
            print("Tasks currently running: ", len(asyncio.all_tasks()))

    async def main():
        """Main function for testing."""
        # asyncio.create_task(monitor())
        flip = 0
        serve_addr = 2345
        serve_addr2 = 2346
        client_addr2 = 1233
        client_addr = 1234
        if flip:
            t = serve_addr
            serve_addr = client_addr
            client_addr = t

            t = serve_addr2
            serve_addr2 = client_addr2
            client_addr2 = t

        loop = asyncio.get_event_loop()
        my_node = Node(loop)

        address = Star_Address("tcp", "127.0.0.1", serve_addr)
        tcp_ip_interface = Generic_TCP(address)

        address2 = Star_Address("tcp", "127.0.0.1", serve_addr2)
        tcp_ip_interface2 = Generic_TCP(address2)

        # enables this transport. A serve socket and a connection out socket.
        await my_node.add_transport(tcp_ip_interface)
        await my_node.add_transport(tcp_ip_interface2)

        name = await asyncio.to_thread(input, "Wait...... ")
        address_to = Star_Address("tcp", "127.0.0.1", client_addr)
        address_to2 = Star_Address("tcp", "127.0.0.1", client_addr2)

        headers = {"METHOD": "PING"}
        await my_node.send_to(
            tcp_ip_interface, address_to, headers, "Client Request 1"
        )  # async.
        await my_node.send_to(
            tcp_ip_interface2, address_to2, headers, "Client Request 2"
        )  # async.

        await my_node.send_to(
            tcp_ip_interface, address_to2, headers, "Client Request 3"
        )  # async.
        await my_node.send_to(
            tcp_ip_interface2, address_to, headers, "Client Request 4"
        )  # async.

        await asyncio.sleep(1000)

    asyncio.run(main())
