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
import sys
import logging

from src.core.io_host import Device

try:
    from src.core.io_host import TelNetConsoleHost
    import src.core.star_components as star
    from src.util.util import compress_str_to_bytes
except:

    class TelNetConsoleHost:
        pass


logger = logging.getLogger(__name__)


class Node:
    pass


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
    def __init__(self, parser: argparse._SubParsersAction, writer: asyncio.Queue):
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
            "user",
            help="start a shell for user connected to this device",
        )
        shell_attach.set_defaults(func=self.shell_attach)
        self.writer = writer

    async def shell_attach(self, args):
        s = f"Attaching a shell for user: {args.user} to this device\n"
        await self.writer.put(s.encode("utf-8"))


class ProcProcessor:
    def __init__(self, parser: argparse._SubParsersAction, writer: asyncio.Queue):
        proc_parser = parser.add_parser(
            "proc", description="Commands to manage registered processes in StarfishOS"
        )
        proc_sub = proc_parser.add_subparsers(
            help="Kernel process control command to execute"
        )
        proc_sub.required = True
        proc_ls: argparse.ArgumentParser = proc_sub.add_parser(
            "ls",
            description="List tasks in engine",
        )
        proc_start: argparse.ArgumentParser = proc_sub.add_parser(
            "start", description="Start task from kernel"
        )
        self.writer = writer
        # ls options

        proc_ls.add_argument(
            "-a",
            "--all",
            action="store_true",
            help="Retrieve all processes from network",
        )
        proc_ls.add_argument(
            "-e",
            "--everyone",
            action="store_true",
            help="Include all users' processes (everyone)",
        )

        proc_start.add_argument("starprogram", help="Path to star file")
        proc_start.add_argument(
            "-u", "--user", help="User to run the process in", required=True
        )
        proc_ls.set_defaults(func=self.proc_ls)
        proc_start.set_defaults(func=self.proc_start)

    async def proc_ls(self, args):
        logger.info("KERNEL - Process List command")
        out = f"Process List - All: {args.all} - Everyone: {args.everyone}\n"
        await self.writer.put(out.encode("utf-8"))

    async def proc_start(self, args):
        out = f"Process Start - {args.starprogram} - User: {args.user}\n"
        await self.writer.put(out.encode("utf-8"))


class PeerProcessor:
    def __init__(self, parser: argparse._SubParsersAction, writer: asyncio.Queue):
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

    async def peer_ls(self, args):
        out = f"Peer ls\n"
        await self.writer.put(out.encode("utf-8"))

    async def peer_connect(self, args):
        out = f"Peer Connect to {args.peer} to transport {args.transport}\n"
        await self.writer.put(out.encode("utf-8"))


class IOProcessor:
    def __init__(self, parser: argparse._SubParsersAction, writer: asyncio.Queue):
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
        io_ls: argparse.ArgumentParser = file_sub.add_parser(
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
        file_ls.add_argument(
            "-e",
            "--everyone",
            action="store_true",
            help="Include all users' files (everyone)",
        )

        io_ls.add_argument(
            "-a",
            "--all",
            action="store_true",
            help="Retrieve all device IDs from network",
        )
        io_ls.add_argument(
            "-e",
            "--everyone",
            action="store_true",
            help="Include all users' devices (everyone)",
        )

    async def file_ls(self, args):
        out = f"File List - All: {args.all} - Everyone: {args.everyone}\n"
        await self.writer.put(out.encode("utf-8"))

    async def io_ls(self, args):
        out = f"Device List - All: {args.all} - Everyone: {args.everyone}\n"
        await self.writer.put(out.encode("utf-8"))


class StatProcessor:
    def __init__(self, parser: argparse._SubParsersAction, writer: asyncio.Queue):
        ex_parse = parser.add_parser("exit", description="Exit kernel mode")
        stat_parse: argparse.ArgumentParser = parser.add_parser(
            "stat", description="Exit kernel mode"
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

    async def stat(self, args):
        out = f"Stats: Task:{args.task} File:{args.file} KeepAlive:{args.keepalive} Network:{args.network}"
        await self.writer.put(out.encode("utf-8"))


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

        self.shell = ShellProcessor(subparsers, None)  # type: ignore
        self.proc = ProcProcessor(subparsers, None)  # type: ignore
        self.peer_p = PeerProcessor(subparsers, None)  # type: ignore
        self.io_p = IOProcessor(subparsers, None)  # type: ignore
        self.exit_p = StatProcessor(subparsers, None)  # type: ignore
        self.node = node
        self.reader = reader
        self.writer = writer
        self.telnet = tel

    async def run(self):
        # listen to kernel reader for command.
        # write out to kernel writer
        did_start_shell = False
        while True:
            device, command_line_b = await self.reader.get()
            local_writer = self.writer[device]
            command_line = command_line_b.decode("utf-8")
            if command_line == "exit":
                await self.telnet.exit_kernel(device)
                if not (did_start_shell):
                    pgrm = star.Program(read_pgrm="examples/shell.star")
                    logger.info(
                        f"Opening program '{pgrm.saved_data['pgrm_name']}' from {pgrm.saved_data['date_compiled']}\n"
                    )
                    usr_name = "Ben"
                    usr = compress_str_to_bytes(usr_name)
                    process = await self.node.start_program(pgrm, usr)
                    did_start_shell = True
                continue

            if command_line != "":
                output = await self.process_command(command_line, device)
                await local_writer.put(output.encode("utf-8"))
            await local_writer.put(
                "\n[dark_goldenrod]kernel# [/dark_goldenrod]".encode("utf-8")
            )

    async def process_command(self, command: str, device: Device):
        self.shell.writer = self.writer[device]
        self.proc.writer = self.writer[device]
        self.peer_p.writer = self.writer[device]
        self.io_p.writer = self.writer[device]
        self.exit_p.writer = self.writer[device]

        items = command.split(" ")
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
