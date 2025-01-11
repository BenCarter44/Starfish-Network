"""
Starfish OS - A distributed OS

This is a testing script that loads and runs a STAR program. Use this to test STAR programs.

It is just a one-node OS.
"""

import asyncio
import sys
from src.node import Node
import src.core.star_components as star

import logging
from src.util.log_format import CustomFormatter

logger = logging.getLogger(__name__)


if __name__ == "__main__":

    async def main():
        """Main node task"""

        try:
            pgrm_name = sys.argv[1]
        except:
            print(
                "Please pass in a STAR program to run.\n\nExample:\npython3 simple_executor.py examples/my_list_program.star"
            )
            sys.exit(1)

        # asyncio.create_task(monitor())
        tp = star.StarAddress("tcp://127.0.0.1:9280")
        bin_addr = b"\x00\x22\x00\x05\x04\x03\x02\x01"

        node = Node(bin_addr, tp)
        asyncio.create_task(node.run())
        await asyncio.sleep(1)

        # EDIT HERE to

        try:
            pgrm = star.Program(read_pgrm=pgrm_name)
        except:
            print("\nInvalid or non-existent STAR program. \nExiting.")
            sys.exit(1)

        logger.info(
            f"I: Opening program '{pgrm.saved_data['pgrm_name']}' from {pgrm.saved_data['date_compiled']}\n"
        )
        process = await node.start_program(pgrm, b"User")

        await asyncio.sleep(1000)
        logger.critical("Main done! Shutdown OS.")

    logger = logging.getLogger(__name__)

    # create console handler with a higher log level
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.DEBUG)
    ch.setFormatter(CustomFormatter())
    logging.basicConfig(handlers=[ch], level=logging.WARNING)

    asyncio.get_event_loop().set_debug(True)
    asyncio.run(main())
