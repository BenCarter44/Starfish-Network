# try:
import datetime
import glob
import os
import random
from typing import cast
import uuid
from src.communications.IOService import IOService
from src.communications.KeepAliveService import KeepAliveCommService
from src.communications.PeerService import PeerService
from src.communications.FileService import FileService
from src.communications.primitives_pb2 import TaskValue
from src.core.File import File, HostedFile
from src.core.io_host import Device
from src.core.star_components import Event, Program, StarProcess, StarTask
from src.plugboard import PlugBoard

# except:
#     import plugboard

import asyncio
import logging

import src.util.sim_log as sim
from src.util.util import decompress_bytes_to_str

logger = logging.getLogger(__name__)

DISCOVERY_RATE = 2

import grpc

try:
    from .communications.DHTService import DHTService
    from .communications.TaskService import TaskService
    from .communications.main_pb2_grpc import (
        add_DHTServiceServicer_to_server,
        add_TaskServiceServicer_to_server,
        add_PeerServiceServicer_to_server,
        add_KeepAliveServiceServicer_to_server,
        add_FileServiceServicer_to_server,
        add_IOServiceServicer_to_server,
    )
    from .core.star_components import StarAddress
except:
    from communications.DHTService import DHTService
    from communications.TaskService import TaskService
    from communications.main_pb2_grpc import (
        add_DHTServiceServicer_to_server,
        add_TaskServiceServicer_to_server,
        add_PeerServiceServicer_to_server,
        add_KeepAliveServiceServicer_to_server,
        add_FileServiceServicer_to_server,
        add_IOServiceServicer_to_server,
    )
    from core.star_components import StarAddress


class Node:
    # Support only one transport now!
    def __init__(
        self,
        bin_addr: bytes,
        transport: StarAddress,
        file_save_dir: str,
        public_bind=False,
    ):
        """Host a node.

        Args:
            bin_addr (bytes): The node binary address (Peer ID)
            transport (StarAddress): Transport address to serve on.
        """
        # sim log
        log = sim.SimLogger(bin_addr)
        log.log(sim.LOG_DHT_NODE_CREATE, bin_addr)

        self.plugboard = PlugBoard(bin_addr, transport, file_save_dir, self)
        self.addr = bin_addr
        self.transport = transport
        self.is_connected = False

        # delete all files in save dir.
        for file in glob.glob(f"{file_save_dir}/*.stg"):
            logger.debug(f"FILE - Deleting previous {file}")
            os.unlink(file)
        for file in glob.glob(f"{file_save_dir}/*.stm"):
            logger.debug(f"FILE - Deleting previous {file}")
            os.unlink(file)

        self.public_bind = public_bind

    async def run(self):
        """Run the gRPC servers and start the execution engine"""
        asyncio.create_task(self.plugboard.engine.start_loops())

        self.server = grpc.aio.server(maximum_concurrent_rpcs=None)
        add_DHTServiceServicer_to_server(
            servicer=DHTService(
                self.plugboard, self.addr, self.plugboard.keep_alive_manager
            ),
            server=self.server,
        )
        add_TaskServiceServicer_to_server(
            servicer=TaskService(
                self.plugboard,
                self.addr,
                self.plugboard.keep_alive_manager,
            ),
            server=self.server,
        )
        add_PeerServiceServicer_to_server(
            servicer=PeerService(
                self.plugboard,
                self.addr,
                self.plugboard.keep_alive_manager,
            ),
            server=self.server,
        )
        add_KeepAliveServiceServicer_to_server(
            servicer=KeepAliveCommService(
                self.plugboard,
                self.addr,
                self.plugboard.get_kp_man(),
            ),
            server=self.server,
        )
        add_FileServiceServicer_to_server(
            servicer=FileService(
                self.plugboard,
                self.addr,
                self.plugboard.get_kp_man(),
            ),
            server=self.server,
        )
        add_IOServiceServicer_to_server(
            servicer=IOService(
                self.plugboard,
            ),
            server=self.server,
        )

        port = self.transport.get_string_channel()
        if self.public_bind:
            self.server.add_insecure_port(
                f"0.0.0.0:{self.transport.port.decode('utf-8')}"
            )
            logger.info(f"META - Serving on: 0.0.0.0:9280")
        else:
            self.server.add_insecure_port(port)
            logger.info(f"META - Serving on: {port}")
        await self.server.start()
        asyncio.create_task(self.peer_discovery_task())
        await self.server.wait_for_termination()

    async def connect_to_peer(self, peer_addr: bytes, address: StarAddress):
        """Create bootstrap request to peer.

        Args:
            peer_addr (bytes): Peer ID
            address (StarAddress): Address of peer to connect to
        """
        # send bootstrap request to peer.
        await self.plugboard.perform_bootstrap(peer_addr, address)
        await self.plugboard.add_peer(peer_addr, address)
        self.is_connected = True

    async def peer_discovery_task(self):
        """The peer discovery task. Do round every 5 sec"""
        while True:
            await asyncio.sleep(DISCOVERY_RATE)
            # return
            if self.is_connected or self.plugboard.received_rpcs.is_set():
                await self.plugboard.perform_discovery_round()

    async def get_peerID(self):
        return self.addr

    async def start_program(
        self, program: Program, user_id: bytes, initial_data={}
    ) -> StarProcess:
        """Put a program on the execution queue of the OS

        Args:
            program (Program): Program object
            user_id (bytes): User ID in bytes

        Raises:
            ValueError: Program is malformed

        Returns:
            StarProcess: The process object currently being run.
        """
        task_list: set[StarTask] = program.task_list
        if task_list is None:
            raise ValueError("No tasks in program!")
        if program.start is None:
            raise ValueError("No event to start the program!")

        # create a process. Create a random UUID for the process. It can't conflict
        # with already running processes for the user.
        proc = StarProcess(
            user_id,
            int.to_bytes(random.randint(1, 2**15), 2, "big"),
        )
        for task in task_list:
            proc.add_task(task)

        await self.plugboard.allocate_program(proc)  # includes callable inside.

        # logger.info(f""META - Task DHT of {self.addr.hex()}")
        # print(self.plugboard.task_table.fetch_dict())

        program.start.target.attach_to_process(proc)

        # await asyncio.sleep(100)
        logger.info(f"TASK - Start Event: {program.start.target.get_id().hex()}")
        program.start.nonce = 0
        program.start.data = initial_data
        await self.plugboard.dispatch_event(program.start)
        return proc

    def attach_device_host(self, tl_host):
        self.plugboard.io_host.attach_device_host(tl_host)
        tl_host.star_addr = self.transport

    def process_list(self, network=False, include_tasks=False):
        tasks = self.plugboard.task_table.fetch_dict(network)
        process_out = set()
        out = []
        for key, task in tasks.items():
            tv = TaskValue.FromString(task)
            proc = StarProcess.from_bytes(tv.process_data)
            if include_tasks:
                out.append((tv.address, StarTask.from_bytes(tv.task_data)))

            elif proc.get_id() not in process_out:
                out.append(proc)
                process_out.add(proc.get_id())
        return out

    def peer_list(self):
        peers = self.plugboard.peer_table.fetch_dict()
        out = []
        for key, value in peers.items():
            address = StarAddress.from_bytes(value)

            str_channel = address.get_string_channel()
            last_seen = "Not Connected"
            if str_channel in self.plugboard.keep_alive_manager.channels:
                channel = self.plugboard.keep_alive_manager.channels[str_channel]
                dt = datetime.datetime.fromtimestamp(channel.last_seen)
                last_seen = str(dt)
            out.append((key, str_channel, last_seen))
        return out

    def file_list(self, network=False):
        file_table = self.plugboard.file_table.fetch_dict(network)
        out = []
        for key, value in file_table.items():
            hf = HostedFile.from_key(key)
            out.append(
                (key, value, decompress_bytes_to_str(hf.get_user()), hf.get_filepath())
            )
        return out

    def io_list(self, network=False):
        device_table = self.plugboard.device_table.fetch_dict()
        out = []
        for key, value in device_table.items():
            dev = Device.from_id(key)
            if not (network) and value != self.addr:
                continue
            out.append((key, value, dev.get_name()))
        self.plugboard.device_table.fancy_print()
        return out

    # async def set_file(self, user, filename, data):
    #     hf = HostedFile(user, filename)
    #     await self.plugboard.create_file(hf)
