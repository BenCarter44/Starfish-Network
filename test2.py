import asyncio
import sys
from src.node import Node
import src.core.star_components as star

import logging

logger = logging.getLogger(__name__)


if __name__ == "__main__":

    class CustomFormatter(logging.Formatter):
        grey_dark = "\x1b[38;5;7m"
        grey = "\x1b[38;5;123m"
        yellow = "\x1b[33;20m"
        red = "\x1b[31;20m"
        bold_red = "\x1b[1m\x1b[38;5;9m"
        reset = "\x1b[0m"
        format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s (%(filename)s:%(lineno)d)"  # type: ignore

        FORMATS = {
            logging.DEBUG: grey_dark + format + reset,  # type: ignore
            logging.INFO: grey + format + reset,  # type: ignore
            logging.WARNING: yellow + format + reset,  # type: ignore
            logging.ERROR: red + format + reset,  # type: ignore
            logging.CRITICAL: bold_red + format + reset,  # type: ignore
        }

        def format(self, record):  # type: ignore
            log_fmt = self.FORMATS.get(record.levelno)
            formatter = logging.Formatter(log_fmt)
            return formatter.format(record)

    async def monitor():
        """Get a count of how many tasks scheduled on the asyncio loop."""
        while True:
            await asyncio.sleep(1)
            logger.debug(f"Tasks currently running: {len(asyncio.all_tasks())}")

    async def main():
        # asyncio.create_task(monitor())
        mode = sys.argv[1]
        server_number = int(mode)
        logger.info(f"SERVE: {server_number}")

        """Main function for testing."""
        # asyncio.create_task(monitor())
        addr_table = [
            (
                b"\x00\x22\x00\x00\x00\x00\x00\x00\x00\x00\x00\x05\x04\x03\x02\x01",
                star.StarAddress("tcp://127.0.0.1:9280"),
            ),
            (
                b"\x40\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01",
                star.StarAddress("tcp://127.0.0.1:9281"),
            ),
            (
                b"\x80\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01",
                star.StarAddress("tcp://127.0.0.1:9282"),
            ),
            (
                b"\xB0\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01",
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

            await asyncio.sleep(2)
            logger.info("Final Node1 PEER LIST")
            print(node.plugboard.peer_table.fetch_copy())

        # if server_number == 2:

        #     logger.info("Connecting Addr#1 to Addr#3")
        #     await node.establish_connection(b"AddrThree", addr_table[b"AddrThree"])
        #     await node.establish_connection(b"AddrFour", addr_table[b"AddrFour"])

        #     logger.info("Final Node1")
        #     print(node.peer_dht.fetch_copy())

        if server_number == 1:
            pgrm = star.Program(read_pgrm="examples/my_list_program.star")
            logger.info(
                f"I: Opening program '{pgrm.saved_data['pgrm_name']}' from {pgrm.saved_data['date_compiled']}\n"
            )
            process = await node.start_program(pgrm, b"User")

        # elif server_number == 2:
        #     await asyncio.sleep(10)
        #     pgrm = star.Program(read_pgrm="file_program.star")
        #     logger.info(
        #         f"I: Opening program '{pgrm.saved_data['pgrm_name']}' from {pgrm.saved_data['date_compiled']}\n"
        #     )
        #     process = await node.start_program(pgrm)

        await asyncio.sleep(1000)
        logger.critical("Main done!")

    logger = logging.getLogger(__name__)

    # # create console handler with a higher log level
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.DEBUG)
    ch.setFormatter(CustomFormatter())
    logging.basicConfig(handlers=[ch], level=logging.DEBUG)

    asyncio.get_event_loop().set_debug(True)
    asyncio.run(main())
