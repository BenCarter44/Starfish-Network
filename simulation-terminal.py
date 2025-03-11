import asyncio
import io
import time
import telnetlib3

from src.core.star_components import StarAddress


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

    async def get_header(self):
        return await self.queue_out.get()

    async def close(self):
        """Closes the connection."""
        await self.send_command(None)  # Signal to stop processing queue


class KernelController:
    def __init__(self, tel: Terminal):
        self.tel = tel

    def connect_to_peer(self, peerID: bytes, transport: StarAddress):
        self.tel.send_command(
            f"peer connect -p {peerID.hex(sep=':')} -t {transport.get_string_channel()}"
        )

    def start_program(self, pgrm_name: str, usr: str):
        self.tel.send_command(f"proc start {pgrm_name} -u {usr}")


async def main():
    tel = Terminal("localhost", 2321)
    await tel.open()
    await asyncio.sleep(20)
    await tel.close()


if __name__ == "__main__":
    asyncio.run(main(), debug=True)
