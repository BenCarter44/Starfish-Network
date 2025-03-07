"""
Starfish OS - A decentralized & distributed OS
Benjamin Carter - 3/6/2025

This script consists of the main entry point for creating a node.

CLI:
main.py -h
    Show help
main.py -a 12:12:12:12:12:12:12:12 -t tcp://127.0.0.1:9820 -i 2321
    Set peer address
    Set transport for node communications (default: tcp://127.0.0.1:9820)
    Set I/O Telnet Port (default: 2321)
main.py -a 12:12:12:12:12:12:12:12 -s savedirectory/
    Set peer address
    Set file save directory (default: filestorage/)
main.py (same as above) -v 1
    Set verbosity. 0 to 4.
"""

import argparse
import sys

from src.KernelCommands import KernelCommandProcessor
from src.core.io_host import TelNetConsoleHost
from src.core.star_components import StarAddress
from src.node import Node

import logging
import asyncio
from src.util.log_format import CustomFormatter

logger = logging.getLogger(__name__)


def create_parser():
    parser = argparse.ArgumentParser(
        description="Starfish Node CLI - run a node for the OS.", epilog="Starfish OS"
    )

    parser.add_argument(
        "-a", "--address", required=True, help="Set peer address (Required)"
    )
    parser.add_argument(
        "-t",
        "--transport",
        default="tcp://127.0.0.1:9820",
        help="Set transport address (Default: tcp://127.0.0.1:9820)",
    )
    parser.add_argument(
        "-i",
        "--ioport",
        type=int,
        default=2321,
        help="Set I/O telnet port (Default: 2321)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        type=int,
        default=1,
        help="Set verbose logging value 0-4 (Default: 1)",
    )
    parser.add_argument(
        "-s",
        "--savedir",
        type=str,
        default="filestorage",
        help="Set location to store file artifacts (Default: filestorage/)",
    )
    return parser


async def main(peer_address, star_address, savedir, ioport):

    node = Node(peer_address, star_address, savedir)
    asyncio.create_task(node.run())
    print(f"META - Server up")
    await asyncio.sleep(1)

    tl_host = TelNetConsoleHost(ioport)
    node.attach_device_host(tl_host)

    read_in, write_out = tl_host.get_kernel_queues()  # reader, writer
    kcommand = KernelCommandProcessor(read_in, write_out, node, tl_host)
    asyncio.create_task(kcommand.run())

    await asyncio.sleep(1)
    print(f"META - Telnet up")


if __name__ == "__main__":

    parser = create_parser()
    args = parser.parse_args()
    print("Starting up node....")
    print(f"Peer Address: {args.address}")
    print(f"Transport Address: {args.transport}")
    print(f"I/O Telnet Port: {args.ioport}")
    print(f"Save Directory: {args.savedir}")
    print(f"Verbosity: {args.verbose}")

    logger = logging.getLogger(__name__)

    # create console handler with a higher log level
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.DEBUG)
    ch.setFormatter(CustomFormatter())

    def filter_messages_by_label(record):
        if record.levelno >= logging.ERROR:
            return True
        record.msg = str(record.msg)
        if record.module.startswith("stream_writer"):
            return False
        if record.module.startswith("server"):
            return False
        if record.msg.startswith("PEER"):
            return False
        elif record.msg.startswith("ENGINE"):
            return False
        elif record.msg.startswith("TASK"):
            return True
        elif record.msg.startswith("FILE"):
            return False
        elif record.msg.startswith("DISCOVERY"):
            return False
        elif record.msg.startswith("DHT"):
            return False
        elif record.msg.startswith("IO"):
            return True
        elif record.msg.startswith("KEEPALIVE"):
            return False
        elif record.msg.startswith("META"):
            return False
        return True

    ch.addFilter(filter_messages_by_label)

    peer_address_str = args.address.replace(":", "")
    try:
        peer_address = bytes.fromhex(peer_address_str)
    except:
        sys.stderr.write("Error: Invalid peer address \n")
        sys.exit(1)

    if len(peer_address) != 8:
        sys.stderr.write("Error: Address must be 8 bytes long \n")
        sys.exit(1)

    try:
        star_address = StarAddress(args.transport)
    except:
        sys.stderr.write("Error: Invalid transport address \n")
        sys.exit(1)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    asyncio.get_event_loop().create_task(
        main(peer_address, star_address, args.savedir, args.ioport)
    )

    if args.verbose == 0:
        logging.basicConfig(handlers=[ch], level=logging.ERROR)
        asyncio.get_event_loop().set_debug(False)

    elif args.verbose == 1:
        logging.basicConfig(handlers=[ch], level=logging.ERROR)
        asyncio.get_event_loop().set_debug(True)

    elif args.verbose == 2:
        logging.basicConfig(handlers=[ch], level=logging.WARNING)
        asyncio.get_event_loop().set_debug(True)

    elif args.verbose == 3:
        logging.basicConfig(handlers=[ch], level=logging.INFO)
        asyncio.get_event_loop().set_debug(True)

    elif args.verbose == 4:
        logging.basicConfig(handlers=[ch], level=logging.DEBUG)
        asyncio.get_event_loop().set_debug(True)

    asyncio.get_event_loop().run_forever()
