# Copyright 2020 gRPC authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""The Python AsyncIO implementation of the GRPC helloworld.Greeter client."""

import asyncio
import logging
import sys

logger = logging.getLogger(__name__)


import grpc
from src.communications import main_pb2
from src.communications import main_pb2_grpc
from src.communications.DHTService import DHTClient, DHTService
from src.core.star_components import StarAddress
from src.node import Node
from src.plugboard import PlugBoard


async def run() -> None:
    try:
        async with grpc.aio.insecure_channel("127.0.0.1:9280") as channel:
            dht_client = DHTClient(channel, b"A")
            print("Hello")
            response = await dht_client.StoreItem(b"Key", b"Value", main_pb2.PEER_ID)
        print("Greeter client received: " + str(response))
    except Exception as e:
        print(e)


async def run_server() -> None:
    # server = grpc.aio.server(maximum_concurrent_rpcs=None)
    node = Node(b"A", StarAddress("tcp://127.0.0.1:9280"))
    asyncio.create_task(node.run())

    # main_pb2_grpc.add_DHTServiceServicer_to_server(DHTService(node, b"A"), server)
    # listen_addr = "127.0.0.1:9280"
    # server.add_insecure_port(listen_addr)
    # logging.info("Starting server on %s", listen_addr)
    # await server.start()
    # await server.wait_for_termination()


async def main():
    asyncio.create_task(run_server())
    await asyncio.sleep(2)
    asyncio.create_task(run())
    await asyncio.sleep(200)


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

    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.DEBUG)
    ch.setFormatter(CustomFormatter())
    logging.basicConfig(handlers=[ch], level=logging.DEBUG)

    asyncio.get_event_loop().set_debug(True)
    asyncio.run(main())
