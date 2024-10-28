import asyncio
from typing import cast
import dill  # type: ignore
import logging
from node_queue_interface import Node_Request, Node_Response

logger = logging.getLogger(__name__)

connection_counter = 0
logger.info("HI!")


class Star_Address:
    def __init__(
        self, protocol: str = "tcp", host: str = "127.0.0.1", port: int = 1234
    ):
        """Holds dialing information for a node"""
        self.protocol = protocol
        self.host = host
        self.port = port

    def __eq__(self, other: object):
        if not (isinstance(other, Star_Address)):
            return False

        return (
            self.protocol == other.protocol
            and self.host == other.host
            and self.port == other.port
        )

    def __hash__(self):
        return hash((self.protocol, self.host, self.port))

    def __str__(self):
        return f"{self.protocol}://{self.host}:{self.port}"

    def __repr__(self):
        return self.__str__()


async def TCP_Server(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    output_queue: asyncio.Queue[Node_Request],
    internal_server_queues: dict[int, asyncio.Queue[Node_Response]],
    transport_id: Star_Address,
):
    """ASYNC Callback for when a client connects to the server port of the transport

    Args:
        reader (asyncio.StreamReader): Reader object of stream
        writer (asyncio.StreamWriter): Writer object of stream
        output_queue (asyncio.Queue[Node_Request]): Output Requests sent to node comm.
        internal_server_queues (dict[int, asyncio.Queue[Node_Response]]): Received responses from node comm.
        transport_id (Star_Address): Transport address (an identifier of the transport object calling this)
    """

    global connection_counter

    transport_peer = writer.get_extra_info("peername")
    addr = Star_Address(transport_peer[0], transport_peer[1])
    connection_ID = connection_counter
    internal_server_queues[connection_ID] = asyncio.Queue()
    connection_counter += 1
    logger.debug("Transport: Got connection!")

    # Obtain REQUEST
    request_data = await reader.read()
    request_headers, request_body = dill.loads(request_data)

    routing = {
        "ADDR": addr,
        "CONN_ID": connection_ID,
        "TP_ID": transport_id,
        "SOURCE": "SERVER",
    }
    rq = Node_Request(routing=routing, headers=request_headers, body=request_body)

    await output_queue.put(rq)

    # RESPONSE
    item = await internal_server_queues[connection_ID].get()
    out_data = dill.dumps((item.headers, item.body))
    writer.write(out_data)
    writer.write_eof()
    await writer.drain()

    await asyncio.sleep(0.1)  # TODO: delay for peer to read all the data.
    writer.close()
    await writer.wait_closed()

    # Will need to create protocol framing. USE HTTP Framing!
    #  REQUEST
    #  Headers (len)  # https://h11.readthedocs.io/en/latest/basic-usage.html#http-basics
    #  Body
    #  This then will pass the call directly to the node comm.

    # For now, do  HTTP/1.0 method. Single connection, single request! Later can do multiplexing
    # TODO: [STAR-28] Upgrade to single connection, multiple requests! Do HTTP/1.1
    # Await queue. If node comm sends "SEND", respond.

    # One frame:
    #  REQUEST
    #  Headers (len)
    #  Body

    # Either Client or Server can host one frame at a time.


async def TCP_Client(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    output_queue: asyncio.Queue[Node_Request],
    # internal_client_queues: dict[int, asyncio.Queue[Node_Response]],
    data_request: Node_Response,
    transport_id: Star_Address,
):
    """Client handler once client connects

    Args:
        reader (asyncio.StreamReader): Reader stream object
        writer (asyncio.StreamWriter): Writer stream object
        output_queue (asyncio.Queue[Node_Request]): Queue of Requests to send to node comm
        data_request (Node_Response): The response to send to network
        transport_id (Star_Address): Transport address (an identifier of the transport object calling this)
    """
    global connection_counter

    # internal_client_queues[connection_counter] = asyncio.Queue()
    # original_data_request.connID = connection_counter

    # REQUEST (a response from NodeComm)
    logger.debug(f"SEND OUT: {data_request}")
    out_data = dill.dumps((data_request.headers, data_request.body))
    writer.write(out_data)
    writer.write_eof()
    await writer.drain()

    # RESPONSE (a request to NodeComm)
    read_data = await reader.read()
    response_headers, response_body = dill.loads(read_data)

    writer.close()
    await writer.wait_closed()

    response_routing = {
        "SOURCE": "CLIENT",
        "ORIGINAL": data_request.routing,
        "TP_ID": transport_id,
    }
    resp = Node_Request(
        routing=response_routing, headers=response_headers, body=response_body
    )
    if response_headers.get("METHOD") != "CLOSE":
        await output_queue.put(resp)  # blank response. don't bother node comm.


class Generic_TCP:
    """A basic TCP transport class"""

    def __init__(self, addr: Star_Address):
        self.address = addr
        # for receiving events from the task manager
        self.receiving_queue: asyncio.Queue[Node_Response] = asyncio.Queue()
        # for sending events to the task manager
        self.sending_queue: asyncio.Queue[Node_Request] = asyncio.Queue()
        # for feedback from the task manager
        self.internal_to_server_queue: dict[int, asyncio.Queue[Node_Response]] = {}

    async def initalize_transport(
        self,
        sending_queue: asyncio.Queue[Node_Request],
        receiving_queue: asyncio.Queue[Node_Response],
    ):
        """Alternate constructor for calling by node comm. Initializes Queues.

        Args:
            sending_queue (asyncio.Queue[Node_Request]): To send requests to node comm
            receiving_queue (asyncio.Queue[Node_Response]): To receive requests from node comm
        """
        self.receiving_queue = receiving_queue
        self.sending_queue = sending_queue
        asyncio.create_task(self.run_server())
        asyncio.create_task(self.handle_receiving_queue())

        # runs the server as a separate task.
        # creates a task to monitor the receiving queue for outbound connections

    async def run_server(self):
        """ASYNC TASK. Run the server."""
        server = await asyncio.start_server(
            lambda r, w: TCP_Server(
                r, w, self.sending_queue, self.internal_to_server_queue, self.address
            ),
            self.address.host,
            self.address.port,
        )
        async with server:
            await server.serve_forever()

    async def handle_receiving_queue(self):
        """ASYNC TASK. Handle receiving queue."""
        while True:
            try:
                logger.debug(f"Wait... {id(self.receiving_queue)}")
                item = await self.receiving_queue.get()

                logger.debug(f"Recv {item}")
                x_system = item.routing.get("SYSTEM")
                if x_system is None:
                    logger.warning("No SYSTEM header defined!")
                    continue

                # when node wants new connection.
                if x_system == "CONNECT":
                    x_system_dest = item.routing.get("DEST")
                    if x_system_dest is None:
                        logger.warning("No DEST header defined on CONNECT!")
                        continue
                    addr: Star_Address = x_system_dest
                    asyncio.create_task(
                        self.open_connection(addr, item)
                    )  # non blocking!

                if x_system == "FEEDBACK":
                    x_system_origin = item.routing.get("ORIGINAL")
                    if x_system_origin is None:
                        logger.warning("No ORIGINAL header defined on FEEDBACK!")
                        continue
                    is_to_server = x_system_origin.get("SOURCE")
                    if is_to_server == "CLIENT":
                        logger.warning("Cannot send data from client! Use connect_to()")
                        continue

                    x_system_origin_conn = x_system_origin.get("CONN_ID")
                    if x_system_origin_conn is None:
                        logger.warning("No CONN_ID in ORIGINAL")
                        continue
                    assert x_system_origin_conn in self.internal_to_server_queue
                    await self.internal_to_server_queue[x_system_origin_conn].put(item)

            except Exception as e:
                logger.critical(e)

    async def open_connection(self, addr: Star_Address, data_item: Node_Response):
        """ASYNC. Open connection out to address

        Args:
            addr (Star_Address): Address to connect to
            data_item (Node_Response): Response to send to connection.
        """
        reader, writer = await asyncio.open_connection(
            host=addr.host,
            port=addr.port,
        )
        await TCP_Client(
            reader,
            writer,
            self.sending_queue,
            # self.internal_to_client_queue,
            data_item,
            self.address,
        )


if __name__ == "__main__":

    async def main():
        general_tcp_transport = Generic_TCP(asyncio.get_event_loop())
        # asyncio.create_task(general_tcp_transport.run_server("127.0.0.1", 7373))
        asyncio.create_task(general_tcp_transport.open_connection("127.0.0.1", 7373))
        await asyncio.sleep(200)

    asyncio.run(main())
