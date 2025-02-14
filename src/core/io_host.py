# acts as the IO device host (runs on the node itself.)

# hosts a GRPC server
# hosts a TelNet3 server

import asyncio
import telnetlib3
from io import StringIO
from rich.console import Console


class Device:
    def __init__(self, pathname: str):
        self.name = pathname

    def get_name(self):
        return self.name


class IOHost:
    def __init__(self):
        self.counter = 0

    def attach_device_host(self, tl_host: "TelNetConsoleHost"):
        print("Attach device host")
        tl_host.allocate_device = lambda: self.allocate_device("t")
        tl_host.deallocate_device = self.deallocate_device

    def allocate_device(self, stub: str):
        print("Allocate device")
        self.counter += 1
        return Device(f"/dev/{stub}{self.counter}")

    def deallocate_device(self, device):
        return


class TelNetConsoleHost:
    def __init__(self, port=2323):
        coro = telnetlib3.create_server(port=port, shell=self.receive_connection)
        asyncio.create_task(coro)

        self.allocate_device = None
        self.deallocate_device = None

    # async def run(self, coro):
    #     loop = asyncio.get_event_loop()
    #     server = loop(coro)
    #     loop.run_until_complete(server.wait_closed())

    async def receive_connection(
        self, reader: telnetlib3.TelnetReader, writer: telnetlib3.TelnetWriter
    ):
        print("Got connection")
        device = self.allocate_device()

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
            f"Servicer PeerID: [green1]94-20-5F-20-48-2E-21-21[/green1]", end="\r\n"
        )
        console.print(end="\r\n")
        console.print(
            "[bright_blue bold]userID[/bright_blue bold]:[orange1]/[/orange1]$", end=" "
        )
        writer.write(console.file.getvalue())
        await writer.drain()
        while True:
            reader.is_available()

            inp = await reader.read(1)
            if inp == b"":
                self.deallocate_device(device)
                break  # Done!
            print(inp.encode("ascii"))
            writer.write(inp)
            if inp == "\r":
                if reader.is_available():
                    t = await reader.read(1)  # consume the '\n'

                writer.write("\n")

                console.file.truncate(0)
                console.print(
                    "[bright_blue bold]userID[/bright_blue bold]:[orange1]/[/orange1]$",
                    end=" ",
                )
                writer.write(console.file.getvalue())
            await writer.drain()

        print("Connection done!")


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
    io_host = IOHost()
    tel_host = TelNetConsoleHost()
    io_host.attach_device_host(tel_host)

    await asyncio.sleep(1000)


if __name__ == "__main__":
    asyncio.get_event_loop().set_debug(True)
    asyncio.run(main())
