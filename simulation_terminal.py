import asyncio
import io
import time
import telnetlib3


class StarAddress:
    """Event Struct"""

    def __init__(self, string: str):
        """Hold values that get passed from one task to another

        Args:
            a (Any, optional): A value. Defaults to 0.
            b (Any, optional): B value. Defaults to 0.
        """
        self.protocol = string.split("://", 1)[0]
        self.host = string[len(self.protocol) + 3 :].split(":", 1)[0]
        self.port = int(string.split(":")[-1])
        self.protocol = self.protocol.encode("utf-8")
        self.host = self.host.encode("utf-8")
        self.port = str(self.port).encode("utf-8")
        self.keep_alive = None

    def get_string_channel(self):
        string = f"{self.host.decode('utf-8')}:{self.port.decode('utf-8')}"
        return string


def is_available(stream):
    if isinstance(stream, telnetlib3.TelnetReader):
        return len(stream._buffer) > 0
    elif isinstance(stream, io.BytesIO):
        return stream.getbuffer().nbytes > 0


class Terminal:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.queue = asyncio.Queue()  # Queue for commands
        self.queue_out = asyncio.Queue()  # for output

    async def open(self):
        """Starts the event loop and opens the Telnet connection."""
        print(f"Open: {self.host} {self.port}")
        coro = telnetlib3.open_connection(self.host, self.port, shell=self.handler)
        asyncio.create_task(coro)

    async def handler(
        self, reader: telnetlib3.TelnetReader, writer: telnetlib3.TelnetWriter
    ):
        """Handles incoming data from the server and processes commands from the queue."""

        asyncio.create_task(self.read_processing(reader))
        asyncio.create_task(self.write_processing(writer))

    async def read_processing(self, reader: telnetlib3.TelnetReader):
        while True:
            r = await reader.read(1024)
            await self.queue_out.put(r)

    async def write_processing(self, writer: telnetlib3.TelnetWriter):
        while True:
            r = await self.queue.get()
            if r is None:
                break
            writer.write(r + "\r\n")
            await writer.drain()

        writer.close()

    async def send_command(self, command):
        """Allows synchronous calls to send commands."""
        await self.queue.put(command)

    # async def get_header(self):
    #     return await self.queue_out.get()

    async def close(self):
        """Closes the connection."""
        await self.send_command(None)  # Signal to stop processing queue


class KernelControllerAsync:
    def __init__(self, tel: Terminal):
        self.tel = tel

    async def connect_to_peer(self, peerID: bytes, transport: StarAddress):
        print(
            f"peer connect -p {peerID.hex(sep=':')} -t tcp://{transport.get_string_channel()}"
        )
        await self.tel.send_command(
            f"peer connect -p {peerID.hex(sep=':')} -t tcp://{transport.get_string_channel()}"
        )

    async def start_program(self, pgrm_name: str, usr: str):
        await self.tel.send_command(f"proc start {pgrm_name} -u {usr}")


class SynchronousTerminal:
    def __init__(self, host, port):
        self.tel = Terminal(host, port)
        self.kc = KernelControllerAsync(self.tel)

    def connect_peer(self, peerID: bytes, transport_str: str):
        addr = StarAddress(transport_str)
        asyncio.run(self.run_connect_to_peer(peerID, addr))

    def start_program(self, pgrm: str, usr: str):
        asyncio.run(self.run_start_program(pgrm, usr))

    async def run_connect_to_peer(self, peerID, transport):
        await self.tel.open()
        await asyncio.sleep(2)
        await self.kc.connect_to_peer(peerID, transport)
        await asyncio.sleep(3)
        await self.tel.close()

    async def run_start_program(self, pgrm_name, usr):
        await self.tel.open()
        await asyncio.sleep(2)
        await self.kc.start_program(pgrm_name, usr)
        await asyncio.sleep(3)
        await self.tel.close()
