"""
Starfish OS - A distributed OS

This is a testing script that runs a single node for the operating system.
It is these nodes that interact with other nodes in the network, creating the OS.
"""

import asyncio
import sys
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
            logger.debug(f"Tasks currently running: {len(asyncio.all_tasks())}")

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
                b"\x40\x00\x00\x00\x00\x00\x00\x00",
                star.StarAddress("tcp://127.0.0.1:9281"),
            ),
            (
                b"\x80\x00\x00\x00\x00\x00\x00\x00",
                star.StarAddress("tcp://127.0.0.1:9282"),
            ),
            (
                b"\xB0\x00\x00\x00\x00\x00\x00\x00",
                star.StarAddress("tcp://127.0.0.1:9283"),
            ),
        ]
        if server_number == 1:
            node = Node(addr_table[0][0], addr_table[0][1])
            asyncio.create_task(node.run())

        if server_number == 2:
            node = Node(addr_table[1][0], addr_table[1][1])
            asyncio.create_task(node.run())

        if server_number == 3:
            node = Node(addr_table[2][0], addr_table[2][1])
            asyncio.create_task(node.run())

        if server_number == 4:
            node = Node(addr_table[3][0], addr_table[3][1])
            asyncio.create_task(node.run())

        logger.debug(f"Server up: {server_number}")
        await asyncio.sleep(5)

        if server_number == 1:
            logger.info("Connecting Addr#1 to Addr#2")
            await node.connect_to_peer(addr_table[1][0], addr_table[1][1])

            await asyncio.sleep(5)
            logger.warning("Final Node1 PEER LIST")
            node.plugboard.peer_table.fancy_print()

            logger.warning("Final Keep Alive listening")
            node.plugboard.print_keep_alives()

            logger.warning("Final subscriptions serving")
            node.plugboard.print_cache_subscriptions_serve()

            logger.warning("Final subscriptions listening")
            node.plugboard.print_cache_subscriptions_listening()

        elif server_number == 2:
            await asyncio.sleep(7)
            logger.info("Connecting Addr#2 to Addr#3 & 4")
            await node.connect_to_peer(addr_table[2][0], addr_table[2][1])
            # await node.connect_to_peer(addr_table[3][0], addr_table[3][1])

            logger.warning("Final Node2")
            node.plugboard.peer_table.fancy_print()

            logger.warning("Final Keep Alive listening")
            node.plugboard.print_keep_alives()

            logger.warning("Final subscriptions serving")
            node.plugboard.print_cache_subscriptions_serve()

            logger.warning("Final subscriptions listening")
            node.plugboard.print_cache_subscriptions_listening()

        elif server_number == 3:
            await asyncio.sleep(10)
            logger.info("Connecting Addr#2 to Addr#3 & 4")
            await node.connect_to_peer(addr_table[3][0], addr_table[3][1])
            # await node.connect_to_peer(addr_table[3][0], addr_table[3][1])

            logger.warning("Final Node2")
            node.plugboard.peer_table.fancy_print()

            logger.warning("Final Keep Alive listening")
            node.plugboard.print_keep_alives()

            logger.warning("Final subscriptions serving")
            node.plugboard.print_cache_subscriptions_serve()

            logger.warning("Final subscriptions listening")
            node.plugboard.print_cache_subscriptions_listening()

        if server_number == 4:
            await asyncio.sleep(15)

            logger.warning("Final Node2")
            node.plugboard.peer_table.fancy_print()

            logger.warning("Final Keep Alive listening")
            node.plugboard.print_keep_alives()

            logger.warning("Final subscriptions serving")
            node.plugboard.print_cache_subscriptions_serve()

            logger.warning("Final subscriptions listening")
            node.plugboard.print_cache_subscriptions_listening()

        if server_number == 1:
            pass
            await asyncio.sleep(5)
            pgrm = star.Program(read_pgrm="examples/my_list_program.star")
            logger.info(
                f"I: Opening program '{pgrm.saved_data['pgrm_name']}' from {pgrm.saved_data['date_compiled']}\n"
            )
            process = await node.start_program(pgrm, b"User")

            logger.warning("Final Node1 PEER LIST - task")
            node.plugboard.peer_table.fancy_print()

            logger.warning("Final Node1 TASK LIST - task")
            node.plugboard.task_table.fancy_print()

            logger.warning("Final Keep Alive listening")
            node.plugboard.print_keep_alives()

            logger.warning("Final subscriptions serving")
            node.plugboard.print_cache_subscriptions_serve()

            logger.warning("Final subscriptions listening")
            node.plugboard.print_cache_subscriptions_listening()

        elif server_number == 2:
            pass
            await asyncio.sleep(20)
            logger.warning("Final Node1 TASK LIST - task")
            node.plugboard.task_table.fancy_print()
            # pgrm = star.Program(read_pgrm="examples/file_program.star")
            # logger.info(
            #     f"I: Opening program '{pgrm.saved_data['pgrm_name']}' from {pgrm.saved_data['date_compiled']}\n"
            # )
            # process = await node.start_program(pgrm, b"Bob")

        await asyncio.sleep(1000)
        logger.critical("Main done!")

    logger = logging.getLogger(__name__)

    # create console handler with a higher log level
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.DEBUG)
    ch.setFormatter(CustomFormatter())
    logging.basicConfig(handlers=[ch], level=logging.DEBUG)

    asyncio.get_event_loop().set_debug(True)
    asyncio.run(main())
