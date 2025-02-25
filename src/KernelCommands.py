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

from src.core.io_host import TelNetConsoleHost
import src.core.star_components as star
from src.util.util import compress_str_to_bytes

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
    def __init__(self, parser: argparse._SubParsersAction):
        shell_parser = parser.add_parser(
            "shell",
            description="Commands to control a shell in StarfishOS",
        )
        shell_sub = shell_parser.add_subparsers(
            help="Kernel shell control command to execute"
        )
        shell_sub.required = True
        shell_attach = shell_sub.add_parser(
            "attach", description="Login and attach shell"
        )


class ProcProcessor:
    def __init__(self, parser: argparse._SubParsersAction):
        proc_parser = parser.add_parser(
            "proc", description="Commands to manage registered processes in StarfishOS"
        )
        proc_sub = proc_parser.add_subparsers(
            help="Kernel process control command to execute"
        )
        proc_sub.required = True
        proc_ls = proc_sub.add_parser("ls", description="List tasks in engine")
        proc_start = proc_sub.add_parser("start", description="Start task from kernel")


class PeerProcessor:
    def __init__(self, parser: argparse._SubParsersAction):
        peer_parser = parser.add_parser(
            "peer", description="Commands to manage peer connections in StarfishOS"
        )
        peer_sub = peer_parser.add_subparsers(
            help="Kernel process control command to execute"
        )
        peer_sub.required = True
        peer_ls = peer_sub.add_parser("ls", description="List peers in network")
        peer_connect = peer_sub.add_parser(
            "connect", description="Connect to peer in network, aka bootstrapping"
        )


class IOProcessor:
    def __init__(self, parser: argparse._SubParsersAction):
        fileIO_parser = parser.add_parser(
            "io", description="Commands to manage I/O and Files in StarfishOS"
        )
        file_sub = fileIO_parser.add_subparsers(
            help="Kernel I/O and File command to execute"
        )
        file_sub.required = True
        file_ls = file_sub.add_parser("ls", description="List hosted files and devices")


class ExitDummy:
    def __init__(self, parser: argparse._SubParsersAction):
        ex_parse = parser.add_parser("exit", description="Exit kernel mode")


class KernelCommandProcessor:
    def __init__(
        self,
        reader: asyncio.Queue,
        writer: asyncio.Queue,
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

        self.shell = ShellProcessor(subparsers)
        self.proc = ProcProcessor(subparsers)
        self.peer_p = PeerProcessor(subparsers)
        self.io_p = IOProcessor(subparsers)
        self.exit_p = ExitDummy(subparsers)
        self.node = node
        self.reader = reader
        self.writer = writer
        self.telnet = tel

    async def run(self):
        # listen to kernel reader for command.
        # write out to kernel writer
        did_start_shell = False
        while True:
            command_line_b = await self.reader.get()
            command_line = command_line_b.decode("utf-8")
            if command_line == "exit":
                await self.telnet.exit_kernel()
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
                output = self.process_command(command_line)
                await self.writer.put(output.encode("utf-8"))
            await self.writer.put(
                "\n[dark_goldenrod]kernel# [/dark_goldenrod]".encode("utf-8")
            )

    def process_command(self, command: str):
        items = command.split(" ")
        if items[0] == "kernel":
            items = items[1:]
        if len(items) == 0:
            return ""
        command_input = self.parser.parse_args(items)
        data = self.parser.get_output()
        return data


##################
# Logger - rotating file. Separate program reads the logging directory and pushes it to server
# Logger - gRPC files.
if __name__ == "__main__":
    kc = KernelCommandProcessor(None, None, None)
    while True:
        i = input("kernel# ")
        s = kc.process_command(i)
        print(s)
