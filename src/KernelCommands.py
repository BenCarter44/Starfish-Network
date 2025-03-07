# holds the kernel parsing commands.


# from rich.console import Console

# from rich.table import Table

# table = Table(title="Star Wars Movies")

# table.add_column("Released", justify="right", style="cyan", no_wrap=True)
# table.add_column("Title", style="magenta")
# table.add_column("Box Office", justify="right", style="green")

# table.add_row("Dec 20, 2019", "Star Wars: The Rise of Skywalker", "$952,110,690")
# table.add_row("May 25, 2018", "Solo: A Star Wars Story", "$393,151,347")
# table.add_row("Dec 15, 2017", "Star Wars Ep. V111: The Last Jedi", "$1,332,539,889")
# table.add_row("Dec 16, 2016", "Rogue One: A Star Wars Story", "$1,332,439,889")

# console = Console()
# console.print(table)

import argparse
import asyncio
import io
import shlex
import sys
import logging
from typing import cast
from rich.table import Table

from src.core.io_host import Device
from src.util.util import decompress_bytes_to_str

try:
    from src.core.io_host import TelNetConsoleHost
    import src.core.star_components as star
    from src.util.util import compress_str_to_bytes
except:

    class TelNetConsoleHost:
        pass


# try:
from src.core.star_components import StarAddress, StarProcess, StarTask
from src.node import Node

# except:

#     class Node:
#         pass


def sfill(s, l):
    while len(s) < l:
        s += " "
    return s


logger = logging.getLogger(__name__)


argument_global_output = io.StringIO()


class CapturingArgumentParser(argparse.ArgumentParser):
    """Overwrite argparse to accept file output"""

    def __init__(self, *args, **kwargs):
        super(CapturingArgumentParser, self).__init__(*args, **kwargs)
        self.output = argument_global_output  # this class runs twice!

    def exit(self, status=0, message=None):
        if message:
            self.output.write(message)

    def parse_known_args(self, args=[], namespace=None):
        args = list(args)

        # default Namespace built from parser defaults
        if namespace is None:
            namespace = argparse.Namespace()

        # add any action defaults that aren't present
        for action in self._actions:
            if action.dest is not argparse.SUPPRESS:
                if not hasattr(namespace, action.dest):
                    if action.default is not argparse.SUPPRESS:
                        setattr(namespace, action.dest, action.default)

        # add any parser defaults that aren't present
        for dest in self._defaults:
            if not hasattr(namespace, dest):
                setattr(namespace, dest, self._defaults[dest])

        # parse the arguments - CHANGE - if error, print error
        try:
            namespace, args = self._parse_known_args(args, namespace)
        except argparse.ArgumentError:
            err = argparse._sys.exc_info()[1]
            self.error(str(err))
            return namespace, args

        if hasattr(namespace, argparse._UNRECOGNIZED_ARGS_ATTR):
            args.extend(getattr(namespace, argparse._UNRECOGNIZED_ARGS_ATTR))
            delattr(namespace, argparse._UNRECOGNIZED_ARGS_ATTR)
        return namespace, args

    def print_usage(self, file=None):
        s = self.format_usage()
        self.output.write(s)

    def print_help(self, file=None):
        s = self.format_help()
        self.output.write(s)

    def get_output(self):
        data = self.output.getvalue()
        argument_global_output.truncate(0)
        return data


class ShellProcessor:
    def __init__(
        self,
        parser: argparse._SubParsersAction,
        writer: asyncio.Queue,
        node: Node,
        device: Device,
        tel: TelNetConsoleHost,
    ):
        shell_parser = parser.add_parser(
            "shell",
            description="Commands to control a shell in StarfishOS",
        )
        shell_sub = shell_parser.add_subparsers(
            help="Kernel shell control command to execute"
        )
        shell_sub.required = True
        shell_attach: argparse.ArgumentParser = shell_sub.add_parser(
            "attach", description="Login and attach shell"
        )
        shell_attach.add_argument(
            "-u",
            "--user",
            help="start a shell for user connected to this device",
            required=True,
        )
        shell_attach.set_defaults(func=self.shell_attach)
        self.writer = writer
        self.node = node
        self.device = device
        self.shell_attach_dict: dict[Device, bool] = {}
        self.tel = tel

    async def shell_attach(self, args):
        if args.user is None:
            s = f"[red]Please pass in user parameter[/red]\n"
            await self.writer.put(s.encode("utf-8"))
            return

        # Check if already attached....
        if self.device in self.shell_attach_dict:
            if self.shell_attach_dict[self.device]:
                s = f"[red]A shell is already attached to this device! Disconnect first![/red]\n"
                await self.writer.put(s.encode("utf-8"))
                return

        try:
            uname = compress_str_to_bytes(args.user)
        except:
            out = f"Invalid username!\n"
            await self.writer.put(out.encode("utf-8"))
            return

        pgrm = star.Program(read_pgrm=f"examples/shell.star")

        out = f"Opening program '{pgrm.saved_data['pgrm_name']}' from {pgrm.saved_data['date_compiled']}\n"
        await self.writer.put(out.encode("utf-8"))
        await self.tel.exit_kernel(self.device)
        await self.node.start_program(
            pgrm, uname, {"sys_shell_device": self.device.get_id()}
        )
        self.shell_attach_dict[self.device] = True


class ProcProcessor:
    def __init__(
        self,
        parser: argparse._SubParsersAction,
        writer: asyncio.Queue,
        node: Node,
        device: Device,
    ):
        proc_parser = parser.add_parser(
            "proc", description="Commands to manage registered processes in StarfishOS"
        )
        proc_sub = proc_parser.add_subparsers(
            help="Kernel process control command to execute"
        )
        proc_sub.required = True
        proc_ls: argparse.ArgumentParser = proc_sub.add_parser(
            "ps",
            description="List tasks in engine",
        )
        proc_start: argparse.ArgumentParser = proc_sub.add_parser(
            "start", description="Start task from kernel"
        )
        self.writer = writer
        self.node = node
        # ls options

        proc_ls.add_argument(
            "-a",
            "--all",
            action="store_true",
            help="Retrieve all processes from network",
        )
        proc_ls.add_argument(
            "-t",
            "--task",
            action="store_true",
            help="Retrieve all tasks from network",
        )

        proc_start.add_argument("starprogram", help="Path to star file")
        proc_start.add_argument(
            "-u", "--user", help="User to run the process in", required=True
        )
        proc_ls.set_defaults(func=self.proc_ls)
        proc_start.set_defaults(func=self.proc_start)
        self.device = device

    async def proc_ls(self, args):
        logger.info("KERNEL - Process List command")
        # out = f"Process List - All: {args.all} - Everyone: {args.everyone} - Task: {args.task}\n"
        # await self.writer.put(out.encode("utf-8"))

        data = self.node.process_list(network=args.all, include_tasks=args.task)

        # table = Table(title="Table")
        if args.task:  # is tasks
            # PROCESS/TASK ID | ENGINE PEER | USER ID
            out = " TASK ID" + " " * 17 + "|"
            out += " ENGINE PEER" + " " * 13 + "|"
            out += " USER ID\n"
            out += len(out) * "=" + "\n"
            for engine, task in data:
                task = cast(StarTask, task)
                t_id = task.get_id()
                t_user = task.get_user()
                u = decompress_bytes_to_str(t_user)
                t_engine = engine
                out += f" {t_id.hex(sep='-')} | {t_engine.hex(sep=':').upper()} | {u}\n"
            out += 61 * "=" + "\n"
            await self.writer.put(str(out).encode("utf-8"))
            return

        # PROCESS ID | USER ID
        out = " PROCESS ID" + " " * 14 + "|"
        out += " USER ID\n"
        out += len(out) * "=" + "\n"
        for process in data:
            process = cast(StarProcess, process)
            t_id = process.get_id()
            t_user = process.get_user()
            u = decompress_bytes_to_str(t_user)
            out += f" {t_id.hex(sep='-')} | {u}\n"
        out += 35 * "=" + "\n"
        await self.writer.put(str(out).encode("utf-8"))

    async def proc_start(self, args):
        out = f"Process Start - {args.starprogram} - User: {args.user}\n"
        await self.writer.put(out.encode("utf-8"))
        if args.starprogram is None or args.user is None:
            return
        try:
            uname = compress_str_to_bytes(args.user)
        except:
            out = f"Invalid username!\n"
            await self.writer.put(out.encode("utf-8"))
            return

        try:
            pgrm = star.Program(read_pgrm=f"examples/{args.starprogram}")
        except:
            out = f"[red]Error reading program![/red]\n"
            await self.writer.put(out.encode("utf-8"))
            return
        out = f"Opening program '{pgrm.saved_data['pgrm_name']}' from {pgrm.saved_data['date_compiled']}\n"
        await self.writer.put(out.encode("utf-8"))
        await self.node.start_program(
            pgrm, uname, {"sys_shell_device": self.device.get_id()}
        )


class PeerProcessor:
    def __init__(
        self, parser: argparse._SubParsersAction, writer: asyncio.Queue, node: Node
    ):
        peer_parser = parser.add_parser(
            "peer", description="Commands to manage peer connections in StarfishOS"
        )
        peer_sub = peer_parser.add_subparsers(
            help="Kernel process control command to execute"
        )
        peer_sub.required = True
        peer_ls: argparse.ArgumentParser = peer_sub.add_parser(
            "ls", description="List peers in network"
        )
        peer_ls.add_argument(
            "-a",
            "--all",
            help="Show all peers even if not connected to it",
            action="store_true",
        )

        peer_ls.set_defaults(func=self.peer_ls)
        peer_connect: argparse.ArgumentParser = peer_sub.add_parser(
            "connect", description="Connect to peer in network, aka bootstrapping"
        )
        peer_connect.set_defaults(func=self.peer_connect)
        self.writer = writer

        peer_connect.add_argument("-p", "--peer", help="Peer ID", required=True)
        peer_connect.add_argument(
            "-t", "--transport", help="Transport Address in URL format", required=True
        )
        self.node = node

    async def peer_ls(self, args):
        data = self.node.peer_list()

        # PEER ID | USER ID
        out = " PEER ID" + " " * 17 + "|"
        out += " TRANSPORT" + " " * 12 + "|"
        out += " SEEN" + " " * 22 + "\n"
        out += len(out) * "=" + "\n"
        for peer_id, transport, seen in data:
            if seen == "Not Connected" and not (args.all):
                continue
            out += f" {peer_id.hex(sep=':').upper()} | tcp://{transport} | [grey54]{seen}[/grey54]\n"
        out += 77 * "=" + "\n"
        await self.writer.put(str(out).encode("utf-8"))

    async def peer_connect(self, args):
        out = f"Peer Connect to {args.peer} to transport {args.transport}\n"
        await self.writer.put(out.encode("utf-8"))

        try:
            star_address = StarAddress(args.transport)
            peer = args.peer.replace(":", "")
            peer = bytes(bytearray.fromhex(peer))
            if len(peer) != 8:
                raise ValueError
        except:
            out = "[red]Invalid peer/IP[/red]\n"
            await self.writer.put(out.encode("utf-8"))
            return
        try:
            await self.node.connect_to_peer(peer, star_address)
        except:
            out = "[red]Unable to connect to peer[/red]\n"
            await self.writer.put(out.encode("utf-8"))


class IOProcessor:
    def __init__(
        self, parser: argparse._SubParsersAction, writer: asyncio.Queue, node: Node
    ):
        fileIO_parser = parser.add_parser(
            "file", description="Commands to manage Files in StarfishOS"
        )
        file_sub = fileIO_parser.add_subparsers(help="Kernel File command to execute")
        io_parser = parser.add_parser(
            "io", description="Commands to manage I/O in StarfishOS"
        )
        io_sub = io_parser.add_subparsers(help="Kernel I/O command to execute")
        io_sub.required = True
        file_sub.required = True
        file_ls: argparse.ArgumentParser = file_sub.add_parser(
            "ls", description="List hosted files"
        )
        file_ls.set_defaults(func=self.file_ls)
        io_ls: argparse.ArgumentParser = io_sub.add_parser(
            "ls", description="List hosted I/O devices"
        )
        io_ls.set_defaults(func=self.io_ls)
        self.writer = writer

        file_ls.add_argument(
            "-a",
            "--all",
            action="store_true",
            help="Retrieve all file IDs from network",
        )

        io_ls.add_argument(
            "-a",
            "--all",
            action="store_true",
            help="Retrieve all device IDs from network",
        )
        self.node = node

    async def file_ls(self, args):
        data = self.node.file_list(args.all)

        # PEER ID | USER ID
        out = " FILE ID" + " " * 17 + "|"
        out += " PEER ID" + " " * 17 + "|"
        out += " USER " + " " * 2 + "|"
        out += " PATH " + " " * 2
        out += len(out) * "=" + "\n"
        for file_id, peer_id, user, filepath in data:
            out += f" {file_id.hex('-')} | {peer_id.hex(':').upper()} | {sfill(user,6)} | /{filepath}\n"
        out += 69 * "=" + "\n"
        await self.writer.put(str(out).encode("utf-8"))

    async def io_ls(self, args):
        data = self.node.io_list(args.all)

        # PEER ID | USER ID
        out = " DEVICE ID" + " " * 14 + "|"
        out += " PEER ID" + " " * 17 + "|"
        out += " PATH " + " " * 6
        out += len(out) * "=" + "\n"
        for dev_id, peer_id, filepath in data:
            out += f" {dev_id.hex('-')} | {peer_id.hex(':').upper()} {filepath}\n"
        out += 63 * "=" + "\n"
        await self.writer.put(str(out).encode("utf-8"))


class StatProcessor:
    def __init__(
        self, parser: argparse._SubParsersAction, writer: asyncio.Queue, node: Node
    ):
        ex_parse = parser.add_parser("exit", description="Exit kernel mode")
        stat_parse: argparse.ArgumentParser = parser.add_parser(
            "stat", description="Exit kernel mode"
        )
        stat_parse.add_argument(
            "-p", "--peers", help="Get peer count", action="store_true"
        )
        stat_parse.add_argument(
            "-t", "--task", help="Get task count", action="store_true"
        )
        stat_parse.add_argument(
            "-f", "--file", help="Get file count", action="store_true"
        )
        stat_parse.add_argument("-i", "--io", help="Get IO count", action="store_true")
        stat_parse.add_argument(
            "-k", "--keepalive", help="Get keep-alive count", action="store_true"
        )
        stat_parse.add_argument(
            "-n", "--network", help="Get stats from entire OS", action="store_true"
        )
        stat_parse.set_defaults(func=self.stat)
        self.writer = writer
        self.node = node
        self.device = None

    async def stat(self, args):
        # out = f"Stats: Task:{args.task} File:{args.file} KeepAlive:{args.keepalive} Network:{args.network}"
        # await self.writer.put(out.encode("utf-8"))
        if not (args.task or args.file or args.io or args.peers or args.keepalive):
            args.task = True
            args.file = True
            args.keepalive = True
            args.peers = True
            args.io = True

        # ITEM | Value

        out = f"\nStar Device ID: [orange1]{self.device.get_name()}[/orange1]\n"
        out += (
            f"Servicer PeerID: [green1]{self.node.addr.hex(sep=':').upper()}[/green1]\n"
        )
        out += f"StarAddress: [green1]tcp://{self.node.transport.get_string_channel()}[/green1]\n\n"
        await self.writer.put(str(out).encode("utf-8"))

        out = sfill(" ITEM", 26) + sfill("| VALUE", 14) + "\n"
        out += len(out) * "=" + "\n"
        if args.task:
            ts = self.node.process_list(args.network, True)
            if args.network:
                out += sfill("Tasks known in OS", 26)
            else:
                out += sfill("Tasks in engine", 26)
            out += "| "
            out += str(len(ts))
            out += "\n"
        if args.file:
            ts = self.node.file_list(args.network)
            if args.network:
                out += sfill("Files known in OS", 26)
            else:
                out += sfill("Files stored", 26)
            out += "| "
            out += str(len(ts))
            out += "\n"
        if args.peers:
            ts = self.node.peer_list()
            out += sfill("Known peers", 26)
            out += "| "
            out += str(len(ts))
            out += "\n"
        if args.io:
            ts = self.node.io_list(args.network)
            if args.network:
                out += sfill("Devices known to the OS", 26)
            else:
                out += sfill("Local devices", 26)
            out += "| "
            out += str(len(ts))
            out += "\n"
        if args.keepalive:
            ts = self.node.peer_list()
            temp = []
            for t in ts:
                if t[2] == "Not Connected":
                    continue
                temp.append(t)

            out += sfill("KeepAlive connections", 26)
            out += "| "
            out += str(len(temp))
            out += "\n"

        out += 41 * "=" + "\n"
        await self.writer.put(str(out).encode("utf-8"))

        # number of tasks in exec / # number in total
        # number of files in storage / # number in total
        # number of peers in count
        # number of keepalive connections
        # number of devices in table / # number in total


class KernelCommandProcessor:
    def __init__(
        self,
        reader: asyncio.Queue[tuple[Device, bytes]],
        writer: dict[Device, asyncio.Queue],
        node: Node,
        tel: TelNetConsoleHost,
    ):
        self.parser = CapturingArgumentParser(
            prog="kernel",
            description="control node-specific properties",
            epilog="StarfishOS",
            exit_on_error=False,
        )
        subparsers = self.parser.add_subparsers(help="Kernel command to execute")
        subparsers.required = True

        self.shell = ShellProcessor(subparsers, None, node, None, tel)  # type: ignore
        self.proc = ProcProcessor(subparsers, None, node, None)  # type: ignore
        self.peer_p = PeerProcessor(subparsers, None, node)  # type: ignore
        self.io_p = IOProcessor(subparsers, None, node)  # type: ignore
        self.exit_p = StatProcessor(subparsers, None, node)  # type: ignore
        self.node = node
        self.reader = reader
        self.writer = writer
        self.telnet = tel

    async def run(self):
        # listen to kernel reader for command.
        # write out to kernel writer
        while True:
            device, command_line_b = await self.reader.get()
            local_writer = self.writer[device]
            command_line = command_line_b.decode("utf-8")
            if command_line == "exit":
                if not (self.shell.shell_attach_dict.get(device)):
                    output = "[red]No shell attached, please attach shell first\n"
                    await local_writer.put(output.encode("utf-8"))
                    command_line = ""
                else:
                    await self.telnet.exit_kernel(device)
                    continue

            if command_line != "":
                output = await self.process_command(command_line, device)
                await local_writer.put(output.encode("utf-8"))

            count = len(self.node.peer_list())

            if count < 4:  # needs 2. 3 warning
                await local_writer.put(
                    "\n[red]Warning! Low peer count! Please connect to more peers![/red]".encode(
                        "utf-8"
                    )
                )
                logger.warning("META - Low peer count! Connect to more!")
            await local_writer.put(
                "\n[dark_goldenrod]kernel# [/dark_goldenrod]".encode("utf-8")
            )

    async def process_command(self, command: str, device: Device):
        self.shell.writer = self.writer[device]
        self.shell.device = device
        self.proc.writer = self.writer[device]
        self.proc.device = device
        self.peer_p.writer = self.writer[device]
        self.io_p.writer = self.writer[device]
        self.exit_p.writer = self.writer[device]
        self.exit_p.device = device

        if command == "--SHELL_DISCONNECT--":
            self.shell.shell_attach_dict[device] = False
            return ""
        # items = command.split(" ")
        items = shlex.split(command)
        if items[0] == "kernel":
            items = items[1:]
        if len(items) == 0:
            return ""
        command_input = self.parser.parse_args(items)
        if "func" in command_input:
            await command_input.func(command_input)
        data = self.parser.get_output()
        return data


##################
# Logger - rotating file. Separate program reads the logging directory and pushes it to server
# Logger - gRPC files.
if __name__ == "__main__":
    kc = KernelCommandProcessor(None, None, None, None)
    while True:
        i = input("kernel# ")
        s = kc.process_command(i)
        print(s)
