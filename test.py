"""
Starfish OS - A distributed OS

This is a testing script that runs a single node for the operating system.
It is these nodes that interact with other nodes in the network, creating the OS.
"""

import asyncio
import os
import sys
from src.KernelCommands import KernelCommandProcessor
from src.core.io_host import TelNetConsoleHost
from src.node import Node
import src.core.star_components as star

import logging
from src.util.log_format import CustomFormatter

logger = logging.getLogger(__name__)


if __name__ == "__main__":

    async def monitor():
        """Get a count of how many tasks scheduled on the asyncio loop."""
        while True:
            await asyncio.sleep(1)
            logger.debug(f"META - Tasks currently running: {len(asyncio.all_tasks())}")

    async def main():
        """Main node task"""
        try:
            mode = sys.argv[1]
        except:
            print("Please pass in the node number (1-4) like this: python3 test.py 1")
            sys.exit(1)

        server_number = int(mode)
        logger.info(f"SERVE: {server_number}")

        # asyncio.create_task(monitor())
        addr_table = [
            (
                b"\x00\x22\x00\x05\x04\x03\x02\x01",
                star.StarAddress("tcp://127.0.0.1:9280"),
            ),
            (
                b"\x18\x00\x00\x00\x00\x00\x00\x00",
                star.StarAddress("tcp://127.0.0.1:9281"),
            ),
            (
                b"\x30\x00\x00\x00\x00\x00\x00\x00",
                star.StarAddress("tcp://127.0.0.1:9282"),
            ),
            (
                b"\x48\x00\x00\x00\x00\x00\x00\x00",
                star.StarAddress("tcp://127.0.0.1:9283"),
            ),
            (
                b"\x60\x00\x00\x00\x00\x00\x00\x00",
                star.StarAddress("tcp://127.0.0.1:9284"),
            ),
            (
                b"\x78\x00\x00\x00\x00\x00\x00\x00",
                star.StarAddress("tcp://127.0.0.1:9285"),
            ),
            (
                b"\x90\x22\x00\x05\x04\x03\x02\x01",
                star.StarAddress("tcp://127.0.0.1:9286"),
            ),
            (
                b"\xA8\x00\x00\x00\x00\x00\x00\x00",
                star.StarAddress("tcp://127.0.0.1:9287"),
            ),
            # (
            #     b"\xC0\x00\x00\x00\x00\x00\x00\x00",
            #     star.StarAddress("tcp://127.0.0.1:9288"),
            # ),
            # (
            #     b"\xD0\x00\x00\x00\x00\x00\x00\x00",
            #     star.StarAddress("tcp://127.0.0.1:9289"),
            # ),
            # (
            #     b"\xE0\x00\x00\x00\x00\x00\x00\x00",
            #     star.StarAddress("tcp://127.0.0.1:9290"),
            # ),
            # (
            #     b"\xF0\x00\x00\x00\x00\x00\x00\x00",
            #     star.StarAddress("tcp://127.0.0.1:9291"),
            # ),
        ]
        node = Node(
            addr_table[server_number - 1][0],
            addr_table[server_number - 1][1],
            f"filestorage/{server_number}",
        )
        asyncio.create_task(node.run())

        logger.debug(f"META - Server up: {server_number}")
        await asyncio.sleep(5)

        # if server_number == 1:

        tl_host = TelNetConsoleHost(2320 + server_number)
        node.attach_device_host(tl_host)

        read_in, write_out = tl_host.get_kernel_queues()  # reader, writer

        kcommand = KernelCommandProcessor(read_in, write_out, node, tl_host)
        asyncio.create_task(kcommand.run())

        # logger.info("Connecting Addr#1 to Addr#2")
        # await node.connect_to_peer(addr_table[1][0], addr_table[1][1])

        # await asyncio.sleep(5)
        # logger.warning("Final Node1 PEER LIST")
        # node.plugboard.peer_table.fancy_print()

        # logger.warning("Final Keep Alive listening")
        # node.plugboard.print_keep_alives()

        # logger.warning("Final subscriptions serving")
        # node.plugboard.print_cache_subscriptions_serve()

        # logger.warning("Final subscriptions listening")
        # node.plugboard.print_cache_subscriptions_listening()

        # elif server_number == 2:
        #     await asyncio.sleep(7)
        #     logger.info("Connecting Addr#2 to Addr#3 & 4")
        #     await node.connect_to_peer(addr_table[2][0], addr_table[2][1])
        #     await node.connect_to_peer(addr_table[3][0], addr_table[3][1])

        #     logger.warning("Final Node2")
        #     node.plugboard.peer_table.fancy_print()

        #     logger.warning("Final Keep Alive listening")
        #     node.plugboard.print_keep_alives()

        #     logger.warning("Final subscriptions serving")
        #     node.plugboard.print_cache_subscriptions_serve()

        #     logger.warning("Final subscriptions listening")
        #     node.plugboard.print_cache_subscriptions_listening()

        # elif server_number == 3:
        #     await asyncio.sleep(10)
        #     logger.info("Connecting Addr#2 to Addr#3 & 4")
        #     await node.connect_to_peer(addr_table[3][0], addr_table[3][1])
        #     await node.connect_to_peer(addr_table[4][0], addr_table[4][1])
        #     await node.connect_to_peer(addr_table[5][0], addr_table[5][1])

        #     logger.warning("Final Node2")
        #     node.plugboard.peer_table.fancy_print()

        #     logger.warning("Final Keep Alive listening")
        #     node.plugboard.print_keep_alives()

        #     logger.warning("Final subscriptions serving")
        #     node.plugboard.print_cache_subscriptions_serve()

        #     logger.warning("Final subscriptions listening")
        #     node.plugboard.print_cache_subscriptions_listening()

        # if server_number == 4:
        #     await asyncio.sleep(15)
        #     await node.connect_to_peer(addr_table[6][0], addr_table[6][1])
        #     await node.connect_to_peer(addr_table[7][0], addr_table[7][1])
        #     # await node.connect_to_peer(addr_table[8][0], addr_table[8][1])
        #     # await node.connect_to_peer(addr_table[9][0], addr_table[9][1])
        #     # await node.connect_to_peer(addr_table[10][0], addr_table[10][1])
        #     # await node.connect_to_peer(addr_table[11][0], addr_table[11][1])

        #     logger.warning("Final Node2")
        #     node.plugboard.peer_table.fancy_print()

        #     logger.warning("Final Keep Alive listening")
        #     node.plugboard.print_keep_alives()

        #     logger.warning("Final subscriptions serving")
        #     node.plugboard.print_cache_subscriptions_serve()

        #     logger.warning("Final subscriptions listening")
        #     node.plugboard.print_cache_subscriptions_listening()

        if server_number == 1:
            pass
            # # await asyncio.sleep(10)
            # pgrm = star.Program(read_pgrm="examples/my_program.star")
            # logger.info(
            #     f"I: Opening program '{pgrm.saved_data['pgrm_name']}' from {pgrm.saved_data['date_compiled']}\n"
            # )
            # process = await node.start_program(pgrm, b"Test")

        #     logger.warning("Final Node1 PEER LIST - task")
        #     node.plugboard.peer_table.fancy_print()

        #     logger.warning("Final Node1 TASK LIST - task")
        #     node.plugboard.task_table.fancy_print()

        #     logger.warning("Final Keep Alive listening")
        #     node.plugboard.print_keep_alives()

        #     logger.warning("Final subscriptions serving")
        #     node.plugboard.print_cache_subscriptions_serve()

        #     logger.warning("Final subscriptions listening")
        #     node.plugboard.print_cache_subscriptions_listening()

        # elif server_number == 2:
        #     pass
        #     await asyncio.sleep(20)
        #     logger.warning("Final Node1 TASK LIST - task")
        #     node.plugboard.task_table.fancy_print()

        # pgrm = star.Program(read_pgrm="examples/file_program.star")
        # logger.info(
        #     f"I: Opening program '{pgrm.saved_data['pgrm_name']}' from {pgrm.saved_data['date_compiled']}\n"
        # )
        # process = await node.start_program(pgrm, os.urandom(4))

        #     # pgrm = star.Program(read_pgrm="examples/file_program.star")
        #     # logger.info(
        #     #     f"I: Opening program '{pgrm.saved_data['pgrm_name']}' from {pgrm.saved_data['date_compiled']}\n"
        #     # )
        #     # process = await node.start_program(pgrm, b"Bob")

        # elif server_number in [3, 7, 9, 10]:
        #     pass
        #     await asyncio.sleep(25)
        #     logger.warning("Final Node1 TASK LIST - task")
        #     node.plugboard.task_table.fancy_print()

        #     pgrm = star.Program(read_pgrm="examples/file_program.star")
        #     logger.info(
        #         f"I: Opening program '{pgrm.saved_data['pgrm_name']}' from {pgrm.saved_data['date_compiled']}\n"
        #     )
        #     process = await node.start_program(pgrm, os.urandom(4))

        # elif server_number == 4:
        #     pass
        #     await asyncio.sleep(25)
        #     logger.warning("Final Node1 TASK LIST - task")
        #     node.plugboard.task_table.fancy_print()

        #     pgrm = star.Program(read_pgrm="examples/io_program.star")
        #     logger.info(
        #         f"I: Opening program '{pgrm.saved_data['pgrm_name']}' from {pgrm.saved_data['date_compiled']}\n"
        #     )
        #     process = await node.start_program(pgrm, os.urandom(4))

        await asyncio.sleep(1000)
        logger.critical("Main done!")

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
    logging.basicConfig(handlers=[ch], level=logging.INFO)
    asyncio.get_event_loop().set_debug(True)
    asyncio.run(main())
