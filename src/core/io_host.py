# acts as the IO device host (runs on the node itself.)

# hosts a GRPC server
# hosts a TelNet3 server

import asyncio
import io
from typing import Any, Optional, cast
import dill
import telnetlib3
from io import StringIO
from rich.console import Console
import os
import sys


sys.path.append(os.path.join(os.path.dirname(__file__), "../../"))
try:
    from src.plugboard import PlugBoard
except:
    PlugBoard = int  # type: ignore

from src.core.File import TYPE_IO, HostedFile
import logging

logger = logging.getLogger(__name__)

IO_DETACHED = 100
IO_OK = 200
IO_NONEXIST = 300
IO_BUSY = 400


class Device:
    def __init__(self, peerID: bytes, pathname: str):
        self.name = pathname  # use peerID not userID
        self.device_file = HostedFile(peerID[0:4], pathname, mode=TYPE_IO)
        self.mode = TYPE_IO
        self.peerID = peerID
        self.plugboard_callback: PlugBoard = None  # type: ignore
        self.loop: asyncio.AbstractEventLoop = None  # type: ignore
        self.processID = b""

    def get_name(self):
        return self.name

    def get_id(self) -> bytes:
        return self.device_file.get_key()

    def export(self) -> bytes:
        return dill.dumps((self.get_id(), self.get_local_device_identifier()))

    @classmethod
    def import_packed(cls, export):
        inp = dill.loads(export)
        name_id = inp[0]
        local_id = inp[1]
        c = cls.from_id(name_id)
        c.set_local_id(local_id)
        return c

    @classmethod
    def from_id(cls, dev_id: bytes):

        device_file = HostedFile.from_key(dev_id)
        path_name = device_file.get_filepath()
        user = device_file.get_user()

        return cls(user, path_name)

    def get_peer(self):
        return self.device_file.get_user()

    def set_local_id(self, local_id: bytes):
        self.device_file.local_identifier = local_id

    def get_local_device_identifier(self) -> Optional[bytes]:
        b = self.device_file.get_local_identifier()
        if b == b"":
            return None
        return b

    def __hash__(self):
        return hash(self.device_file.get_key())

    def __eq__(self, other):
        if isinstance(other, Device):
            return self.device_file.get_key() == other.device_file.get_key()
        else:
            return False

    def write(self, data: bytes):
        if self.get_local_device_identifier() is None:
            logger.warning("IO - Write no-exist")
            return IO_NONEXIST
        # get peer ID.
        status = asyncio.run_coroutine_threadsafe(
            self.plugboard_callback.write_handler(self, data), loop=self.loop
        )
        return status.result()

    def read(self, length=-1) -> tuple[bytes, Any]:
        if self.get_local_device_identifier() is None:
            return b"", IO_BUSY
        # get peer ID.
        result = asyncio.run_coroutine_threadsafe(
            self.plugboard_callback.read_handler(self, length), loop=self.loop
        )
        data, status = result.result()
        return data, status

    def read_available(self):
        if self.get_local_device_identifier() is None:
            return False, IO_BUSY
        # get peer ID.
        result = asyncio.run_coroutine_threadsafe(
            self.plugboard_callback.read_available_handler(self), loop=self.loop
        )
        r, s = result.result()
        return r, s

    def open(self):
        # get peer ID.
        result = asyncio.run_coroutine_threadsafe(
            self.plugboard_callback.open_handler(self, self.processID), self.loop
        )
        identifier, status = result.result()

        if status == IO_OK:
            self.set_local_id(identifier)
            return status
        return status

    def close(self):
        if self.get_local_device_identifier() is None:
            return IO_BUSY
        # get peer ID.
        result = asyncio.run_coroutine_threadsafe(
            self.plugboard_callback.close_handler(self), self.loop
        )
        return result.result()

    def unmount(self):
        if self.get_local_device_identifier() is None:
            return IO_BUSY
        # get peer ID.
        result = asyncio.run_coroutine_threadsafe(
            self.plugboard_callback.unmount_handler(self), self.loop
        )
        return result.result()


class IOFactory:
    def __init__(self, plugboard, loop, process_id, engine_id):
        self.plugboard = plugboard
        self.loop = loop
        self.process_id = process_id
        self.engine_id = engine_id

    def IODevice(self, engine_id, filepath: str) -> "Device":
        dev = Device(engine_id, filepath)
        dev.processID = self.process_id
        dev.plugboard_callback = self.plugboard
        dev.loop = self.loop
        logger.info(f"IO - Exe: define IO device {dev.get_id().hex()}")
        return dev

    def IODevice_Import(self, export: bytes) -> "Device":
        dev = Device.import_packed(export)
        dev.plugboard_callback = self.plugboard
        dev.processID = self.process_id
        dev.loop = self.loop
        return dev

    def get_io_constants(self):
        return IO_NONEXIST, IO_BUSY, IO_DETACHED, IO_OK


class IOHost:
    def __init__(self, my_addr: bytes):
        self.counter = 0
        self.my_addr = my_addr
        self.host_alloc_device = None
        self.host_dealloc_device = None

        self.device_sockets: dict[
            Device, list[asyncio.Queue, asyncio.Queue, asyncio.Event, bytearray]
        ] = {}
        self.device_connections: dict[Device, bytes] = {}

    def attach_device_host(self, tl_host: "TelNetConsoleHost"):
        logger.info("IO - Attached device host!")
        tl_host.allocate_device = self.allocate_device
        tl_host.deallocate_device = self.deallocate_device
        tl_host.peerID = self.my_addr

    def open_device_connection(self, device: Device, process_id):
        logger.debug(
            f"IO - Recv open dev connection {device.get_name()} {process_id.hex()}"
        )

        if device not in self.device_connections:
            logger.debug("IO - Detached")
            return b"", IO_DETACHED

        if process_id == self.device_connections[device]:
            logger.debug("IO - OK")
            return process_id, IO_OK

        if self.device_connections[device] == b"":
            self.device_connections[device] = process_id
            logger.debug("IO - OK")
            return process_id, IO_OK

        logger.debug("IO - Busy")
        return b"", IO_BUSY

    def close_device(self, device):
        if device not in self.device_connections:
            return IO_NONEXIST

        if device.get_local_device_identifier() != self.device_connections[device]:
            return IO_BUSY

        self.device_connections[device] = b""
        return IO_OK

    async def allocate_device(self):
        # assumes teletype
        dev = Device(self.my_addr, f"/dev/tty{self.counter}")
        self.counter += 1
        asyncio.create_task(self.host_alloc_device(dev))
        self.device_sockets[dev] = [
            asyncio.Queue(),
            asyncio.Queue(),
            asyncio.Event(),
            bytearray(),
        ]
        self.device_connections[dev] = b""
        return (
            dev,
            self.device_sockets[dev][0],
            self.device_sockets[dev][1],
            self.device_sockets[dev][2],
        )

    async def deallocate_device(self, device):
        if device not in self.device_sockets:
            raise ValueError

        await self.host_dealloc_device(device)
        self.device_sockets[device][2].set()  # alert done!
        del self.device_sockets[device]
        del self.device_connections[device]

    async def unmount_device(self, device: Device):
        if device not in self.device_sockets:
            logger.error("Device not in self.device_events")
            return IO_NONEXIST

        await self.deallocate_device(device)
        return IO_OK

    async def read_device(self, device: Device, length=-1):
        if length == 0:
            return b"", IO_OK
        logger.debug(f"IO - Read challenge: {device.get_id().hex()} {length}")
        if device.get_local_device_identifier() != self.device_connections[device]:
            return b"", IO_BUSY

        while not (self.device_sockets[device][0].empty()):
            try:
                item = self.device_sockets[device][0].get_nowait()
                logger.debug(f"IO - Queue read: {item}")
                self.device_sockets[device][3].extend(item)
            except asyncio.QueueEmpty:
                # done!
                break
            if len(self.device_sockets[device][3]) > length and length != -1:
                break

        logger.debug(f"IO - Read challenge: {self.device_sockets[device][3]}")
        if length < 0:
            b = bytes(self.device_sockets[device][3])
            self.device_sockets[device][3] = bytearray()
        elif length > len(self.device_sockets[device][3]):
            # longer requested than given
            b = bytes(self.device_sockets[device][3])
            self.device_sockets[device][3] = bytearray()
        else:
            b = bytes(self.device_sockets[device][3][:length])
            self.device_sockets[device][3] = self.device_sockets[device][3][length:]

        logger.debug(f"IO - Read challenge out: {b}")

        if self.device_sockets[device][2].is_set():
            return b, IO_DETACHED
        return b, IO_OK

    async def write_device(self, device: Device, data: bytes):
        logger.info(f"IO - Write challenge: {device.get_id().hex()}")
        if device.get_local_device_identifier() != self.device_connections[device]:
            logger.warning(f"IO - Write challenge mismatch")
            return IO_BUSY

        if self.device_sockets[device][2].is_set():
            return IO_DETACHED  # device is closed!

        logger.debug(f"IO - Place data on write queue {data}")
        await self.device_sockets[device][1].put(data)
        return IO_OK

    async def read_available(self, device: Device):
        logger.debug(f"IO - ReadAvail challenge: {device.get_id().hex()}")
        if device.get_local_device_identifier() != self.device_connections[device]:
            return False, IO_BUSY

        if self.device_sockets[device][2].is_set():
            return False, IO_DETACHED  # device is closed!

        out = (
            self.device_sockets[device][0].qsize() > 0
            or len(self.device_sockets[device][3]) > 0
        )
        logger.debug(f"IO - ReadAvail challenge out: {out}")
        return out, IO_OK


def is_available(stream):
    if isinstance(stream, telnetlib3.TelnetReader):
        return len(stream._buffer) > 0
    elif isinstance(stream, io.BytesIO):
        return stream.getbuffer().nbytes > 0


class TelNetConsoleHost:
    def __init__(self, port=2323):
        coro = telnetlib3.create_server(port=port, shell=self.receive_connection)
        asyncio.create_task(coro)
        logger.info(f"IO - TelNetHost open to connections on localhost:{port}")
        self.allocate_device = None
        self.deallocate_device = None
        self.peerID = b""
        self.star_addr = None

        self.kernel_out: asyncio.Queue[tuple[Device, bytes]] = asyncio.Queue()
        self.kernel_in: dict[Device, asyncio.Queue] = {}
        self.is_kernel_enable: dict[Device, bool] = {}

        self.dict_sys_reader: dict[Device, asyncio.Queue] = {}

    def get_kernel_queues(self):
        return self.kernel_out, self.kernel_in

    async def exit_kernel(self, device: Device):
        self.is_kernel_enable[device] = False
        await self.dict_sys_reader[device].put(b"\n")  # causes reset.

    # async def run(self, coro):
    #     loop = asyncio.get_event_loop()
    #     server = loop(coro)
    #     loop.run_until_complete(server.wait_closed())

    async def receive_connection(
        self, reader: telnetlib3.TelnetReader, writer: telnetlib3.TelnetWriter
    ):
        logger.info("IO - Got Connection!")
        device, sys_reader, sys_writer, evt_done = await self.allocate_device()
        device = cast(Device, device)
        sys_reader = cast(asyncio.Queue, sys_reader)
        sys_writer = cast(asyncio.Queue, sys_writer)

        console = Console(
            file=StringIO(), color_system="truecolor", width=80, height=24
        )
        console.print(
            "\r\n[bold]Welcome to the [bright_yellow]Starfish[/bright_yellow] Distributed OS [/bold]",
            end="\r\n",
        )
        console.print("By Benjamin Carter", end="\r\n")
        console.print(
            "Version: 1.2.3.4 - March 25th, 2025",
            end="\r\n",
            highlight=False,
            markup=False,
        )
        console.print(end="\r\n")
        console.print(
            f"Star Device ID: [orange1]{device.get_name()}[/orange1]",
            end="\r\n",
        )
        console.print(
            f"Servicer PeerID: [green1]{self.peerID.hex(sep=':').upper()}[/green1]",
            end="\r\n",
        )
        console.print(
            f"StarAddress: [green1]tcp://{self.star_addr.get_string_channel()}[/green1]",
            end="\r\n",
        )
        console.print(end="\r\n")
        console.print("[dark_goldenrod]kernel# [/dark_goldenrod]", end="")
        # console.print(
        #     "[bright_blue bold]userID[/bright_blue bold]:[orange1]/[/orange1]$", end=" "
        # )
        writer.write(console.file.getvalue())
        await writer.drain()
        logger.info("IO - Creating tasks")

        self.kernel_in[device] = asyncio.Queue()
        self.is_kernel_enable[device] = True
        self.dict_sys_reader[device] = sys_reader

        asyncio.create_task(
            self.reader_processing(
                reader, writer, sys_reader, evt_done, console, device
            )
        )
        asyncio.create_task(
            self.writer_processing(writer, sys_writer, evt_done, console, device)
        )
        # for kernel feedback
        asyncio.create_task(
            self.writer_processing(
                writer, self.kernel_in[device], evt_done, console, device
            )
        )

    async def writer_processing(
        self,
        writer: telnetlib3.TelnetWriter,
        sys_writer: asyncio.Queue,
        queue_done: asyncio.Event,
        console: Console,
        device: Device,
    ):
        logger.info("IO - Writer proc task")
        while not (queue_done.is_set()):
            item: bytes = await sys_writer.get()

            # logger.info(f"IO - Writer proc task recv {s}")
            s = item.decode("utf-8")
            if s == "--SHELL_DISCONNECT--":
                await self.kernel_out.put((device, item))
                self.is_kernel_enable[device] = True
            console.file.truncate(0)
            console.print(s, end="")
            s_out = console.file.getvalue()
            writer.write(s_out.replace("\n", "\r\n"))
            await writer.drain()

        writer.close()
        logger.warning("IO - Closed telnet writer")

    async def reader_processing(
        self,
        reader: telnetlib3.TelnetReader,
        writer: telnetlib3.TelnetWriter,
        sys_reader: asyncio.Queue,
        queue_done: asyncio.Event,
        console: Console,
        device: Device,
    ):
        logger.info("IO - Reader proc task")
        # Break into lines.
        line_buffer = bytearray()
        ignore_space = True
        while True:
            logger.debug("IO - Waiting for read")
            in_str = await reader.read(1024)  # 1KB window size, returns string!
            if len(in_str) == 0:
                break
            # break on '\n'
            for ch in in_str:
                if ch == "\r":
                    is_kernel = (
                        len(line_buffer) >= len("kernel")
                        and line_buffer[0:6] == b"kernel"
                    )

                    if is_kernel or self.is_kernel_enable[device]:
                        self.is_kernel_enable[device] = True
                        logger.info("IO - Enter pressed - submit to kernel")
                        await self.kernel_out.put((device, bytes(line_buffer)))

                    elif not (self.is_kernel_enable[device]):
                        logger.info("IO - Enter pressed - submit to device")
                        await sys_reader.put(bytes(line_buffer))

                    line_buffer.clear()
                    ignore_space = True
                    writer.write("\r\n")
                elif ch == "\n":
                    continue
                elif ch == " " and ignore_space:
                    continue
                elif ch == "\x7f":
                    # backspace
                    if len(line_buffer) > 0:
                        line_buffer.pop()
                        writer.write(ch)  # auto echo
                else:
                    ignore_space = False
                    line_buffer.extend(ch.encode("utf-8"))
                    writer.write(ch)  # auto echo

            if queue_done.is_set():
                break
            await writer.drain()

        logger.info("IO - Detected telnet close!")
        reader.close()
        queue_done.set()
        await self.deallocate_device(device)


# async def shell(reader, writer):
#     writer.write("\r\nWould you like to play a game? ")
#     while True:
#         inp = await reader.read(1)
#         line = ""
#         if inp:
#             writer.echo(inp)
#             await writer.drain()
#             print(inp.encode("utf-8"))
#             continue
#             if inp == "\n":
#                 pass
#             else:
#                 line += inp
#                 continue

#             if line == "exit":
#                 break

#             writer.write("\r\nThey say the only way to win is to not play at all.\r\n")
#             print(line.encode("utf-8"))
#             await writer.drain()
#             line = ""
#         print(f"Null: {inp.encode('utf-8')}")

#     writer.close()


# loop = asyncio.get_event_loop()
# coro = telnetlib3.create_server(port=2323, shell=shell)
# server = loop.run_until_complete(coro)
# loop.run_until_complete(server.wait_closed())


async def main():
    io_host = IOHost(b"abcdefgh")
    tel_host = TelNetConsoleHost()
    io_host.attach_device_host(tel_host)

    await asyncio.sleep(1000)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    asyncio.get_event_loop().set_debug(True)
    asyncio.run(main())


# while True:
#     inp = await reader.read(1)
#     line = ""
#     if inp:
#         writer.echo(inp)
#         await writer.drain()
#         print(inp.encode("utf-8"))
#         continue
#         if inp == "\n":
#             pass
#         else:
#             line += inp
#             continue

#         if line == "exit":
#             break

#         writer.write(
#             "\r\nThey say the only way to win is to not play at all.\r\n"
#         )
#         print(line.encode("utf-8"))
#         await writer.drain()
#         line = ""
#     print(f"Null: {inp.encode('utf-8')}")

# writer.close()
