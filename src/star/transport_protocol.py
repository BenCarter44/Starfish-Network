import asyncio
import binascii
import os
import string
from typing import Optional, cast
import dill  # type: ignore
import logging
import zmq

import zmq.asyncio
from node_queue_interface import Node_Request, Node_Response

logger = logging.getLogger(__name__)

connection_counter = 0
logger.info("HI!")


def dump(msg: list[bytes]) -> None:
    """Display raw output of zmq messages

    Args:
        msg (list[bytes]): zmq multipart message
    """
    for part in msg:
        print("[%03d]" % len(part), end=" ")
        try:
            s_raw = part.decode("ascii")
            for x in s_raw:
                if x not in string.printable:
                    raise ValueError
            print(s_raw)
        except (UnicodeDecodeError, ValueError) as e:
            print(r"0x %s" % (binascii.hexlify(part, " ").decode("ascii")))


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
    transport_id: Star_Address,
    ctx: zmq.asyncio.Context,
    feedback_addr: str,
    control_socket: zmq.asyncio.Socket,
):
    global connection_counter

    transport_peer = writer.get_extra_info("peername")
    addr = Star_Address(transport_peer[0], transport_peer[1])
    connection_ID = str(connection_counter).encode("utf-8")
    connection_counter += 1

    feedback_socket = ctx.socket(zmq.SUB)
    feedback_socket.connect(feedback_addr)
    feedback_socket.subscribe(connection_ID)

    logger.debug("Transport:: Got connection!")

    # Obtain REQUEST
    request_data = await reader.read()
    # with dill.detect.trace():
    request_headers, request_body = dill.loads(request_data)
    routing = {
        "ADDR": addr,
        "CONN_ID": connection_ID,
        "TP_ID": transport_id,
        "SOURCE": "SERVER",
    }
    rq = Node_Request(routing=routing, headers=request_headers, body=request_body)

    logger.debug("Transport:: Send data to node comm. ")
    # FORMAT:
    # 0: bytes: STOP/OK/FEEDBACK
    # 1: routing dill
    # 2: header dill
    # 3: body dill
    await control_socket.send_multipart([b"FEEDBACK"] + rq.get_zmq_message())

    # RESPONSE
    # FORMAT:
    # 0: bytes: ADDR
    # 1: routing dill
    # 2: header dill
    # 3: body dill
    item = await feedback_socket.recv_multipart()
    logger.debug("Transport:: Got response from node comm. Write out")
    headers = dill.loads(item[2])
    body = dill.loads(item[3])
    out_data = dill.dumps((headers, body), fmode=dill.FILE_FMODE, recurse=True)
    writer.write(out_data)
    writer.write_eof()
    await writer.drain()

    # await asyncio.sleep(0.1)  # TODO: delay for peer to read all the data.
    writer.close()
    await writer.wait_closed()
    feedback_socket.close()

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
    data_request: Node_Response,
    transport_id: Star_Address,
    control_socket: zmq.asyncio.Socket,
):
    # REQUEST (a response from NodeComm)

    logger.debug(f"SEND OUT: {data_request}")
    writer.write(data_request.get_dill_data())
    writer.write_eof()
    await writer.drain()
    logger.debug(f"SEND OUT FINISH... waiting for read.")
    await asyncio.sleep(0.1)  # TODO: delay for peer to read all the data.
    # RESPONSE (a request to NodeComm)
    read_data = await reader.read()
    response_headers, response_body = dill.loads(read_data)
    logger.debug(f"SEND OUT FINISH...Got read!")
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
        # FORMAT:
        # 0: bytes: STOP/OK/FEEDBACK
        # 1: routing dill
        # 2: header dill
        # 3: body dill
        b = [b"TERMINAL"] + resp.get_multipart()
        await control_socket.send_multipart(b)


class Generic_TCP:
    """A basic TCP transport class"""

    def __init__(self, addr: Star_Address):
        self.address = addr

    async def attach(
        self, zmq_addr: str, identity: bytes, ctx: Optional[zmq.asyncio.Context] = None
    ):
        if ctx is None:
            self.ctx = zmq.asyncio.Context()
        else:
            self.ctx = ctx

        asyncio.create_task(self.run_server())
        asyncio.create_task(self.run_control())
        # FORMAT:
        # 0: bytes: STOP/OK/FEEDBACK
        # 1: routing dill
        # 2: header dill
        # 3: body dill
        self.control_socket = self.ctx.socket(zmq.DEALER)
        self.control_socket.setsockopt(zmq.IDENTITY, identity)
        self.control_socket.connect(zmq_addr)
        self.socket_to_server = self.ctx.socket(zmq.PUB)
        self.iface = "inproc://%s" % binascii.hexlify(os.urandom(8)).decode("utf-8")
        self.socket_to_server.bind(self.iface)  # for publishing feedback to server.

        # runs the server as a separate task.
        # creates a task to monitor the receiving queue for outbound connections

    async def run_server(self):
        """ASYNC TASK. Run the server."""
        server = await asyncio.start_server(
            lambda r, w: TCP_Server(
                r, w, self.address, self.ctx, self.iface, self.control_socket
            ),
            self.address.host,
            self.address.port,
        )
        async with server:
            await server.serve_forever()

    async def process_control(self, msg: list[bytes]):
        # ROUTING
        # HEADERS
        # BODY
        if len(msg) != 4:
            logger.warning("Malformed message received on proc. control")
            return

        routing = dill.loads(msg[1])  # item.
        headers = dill.loads(msg[2])  # item
        body = dill.loads(msg[3])  # item

        x_system = routing.get("SYSTEM")
        if x_system is None:
            logger.warning("No SYSTEM header defined!")
            return

        # when node wants new connection.
        if x_system == "CONNECT":
            x_system_dest = routing.get("DEST")
            if x_system_dest is None:
                logger.warning("No DEST header defined on CONNECT!")
                return
            addr: Star_Address = x_system_dest
            item = Node_Response.extract_multipart(msg[1:])

            asyncio.create_task(self.open_connection(addr, item))  # non blocking!

        if x_system == "FEEDBACK":
            x_system_origin = routing.get("ORIGINAL")
            if x_system_origin is None:
                logger.warning("No ORIGINAL header defined on FEEDBACK!")
                return
            is_to_server = x_system_origin.get("SOURCE")
            if is_to_server == "CLIENT":
                logger.warning("Cannot send data from client! Use connect_to()")
                return

            x_system_origin_conn = x_system_origin.get("CONN_ID")
            if x_system_origin_conn is None:
                logger.warning("No CONN_ID in ORIGINAL")
                return
            # output to server connection.
            item = Node_Response.extract_multipart(msg[1:])
            await self.socket_to_server.send_multipart(
                [x_system_origin_conn] + item.get_multipart()
            )

    async def run_control(self):
        """ASYNC TASK. Handle receiving commands."""
        while True:
            # FORMAT:
            # 0: bytes: STOP/OK/FEEDBACK
            # 1: routing dill
            # 2: header dill
            # 3: body dill
            msg = await self.control_socket.recv_multipart()
            if msg[0] == b"STOP":
                break
            asyncio.create_task(self.process_control(msg))
        self.control_socket.close()

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
            data_item,
            self.address,
            self.control_socket,
        )


if __name__ == "__main__":

    async def main():
        general_tcp_transport = Generic_TCP(asyncio.get_event_loop())
        # asyncio.create_task(general_tcp_transport.run_server("127.0.0.1", 7373))
        asyncio.create_task(general_tcp_transport.open_connection("127.0.0.1", 7373))
        await asyncio.sleep(200)

    asyncio.run(main())
