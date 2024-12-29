# try:
import random
from typing import cast
import uuid
from src.core.star_components import Program, StarProcess, StarTask
from src.plugboard import PlugBoard

# except:
#     import plugboard

import asyncio
import logging

logger = logging.getLogger(__name__)


import grpc

try:
    from .communications.DHTService import DHTService
    from .communications.TaskService import TaskService
    from .communications.main_pb2_grpc import (
        add_DHTServiceServicer_to_server,
        add_TaskServiceServicer_to_server,
    )
    from .core.star_components import StarAddress
except:
    from communications.DHTService import DHTService
    from communications.TaskService import TaskService
    from communications.main_pb2_grpc import (
        add_DHTServiceServicer_to_server,
        add_TaskServiceServicer_to_server,
    )
    from core.star_components import StarAddress


class Node:
    # Support only one transport now!
    def __init__(self, bin_addr: bytes, transport: StarAddress):
        self.plugboard = PlugBoard(bin_addr, transport)
        self.addr = bin_addr
        self.transport = transport

    async def run(self):
        asyncio.create_task(self.plugboard.engine.start_loops())
        self.server = grpc.aio.server(maximum_concurrent_rpcs=100)
        add_DHTServiceServicer_to_server(
            servicer=DHTService(self.plugboard, self.addr), server=self.server
        )
        add_TaskServiceServicer_to_server(
            servicer=TaskService(self.plugboard, self.addr), server=self.server
        )

        port = self.transport.get_string_channel()
        self.server.add_insecure_port(port)
        logger.info(f"Serving on: {port}")
        await self.server.start()
        await self.server.wait_for_termination()

    async def connect_to_peer(self, peer_addr, address: StarAddress):
        await self.plugboard.add_peer(peer_addr, address)

    async def start_program(self, program: Program, user_id: bytes):
        task_list: set[StarTask] = program.task_list
        if task_list is None:
            raise ValueError("No tasks in program!")
        if program.start is None:
            raise ValueError("No event to start the program!")

        # create a process. Create a random UUID for the process. It can't conflict
        # with already running processes for the user.
        proc = StarProcess(
            user_id,
            int.to_bytes(random.randint(1, 2**15), 8, "big"),
        )
        for task in task_list:
            proc.add_task(task)

        for task in proc.get_tasks():
            await self.plugboard.allocate_task(task)  # includes callable inside.

        # logger.info(f"Task DHT of {self.addr.hex()}")
        # print(self.plugboard.task_table.fetch_copy())

        program.start.target.attach_to_process(proc)
        # await asyncio.sleep(100)
        await self.plugboard.dispatch_event(program.start)
        return proc
