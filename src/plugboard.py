import asyncio
from .core.star_engine import NodeEngine
from .core.DHT import *
from .communications.TaskService import TaskPeer
from .communications.DHTService import DHTClient
from .communications.main_pb2 import DHTSelect, DHTStatus
from .communications.primitives_pb2 import TaskValue
from .core.star_components import StarTask, StarProcess, StarAddress, Event

import grpc

from src.core.star_components import StarTask

import logging

logger = logging.getLogger(__name__)


class PlugBoard:
    def __init__(self, node_id: bytes, local_addr: StarAddress):
        self.my_addr = node_id
        self.engine = NodeEngine(node_id)
        self.engine.send_event_handler = self.dispatch_event

        self.peer_table = DHT(self.my_addr)
        self.peer_table.update_addresses(node_id)
        self.peer_table.set(node_id, local_addr.to_bytes())
        self.task_table = DHT(self.my_addr)
        self.task_table.update_addresses(node_id)
        self.local_addr = local_addr

        channel = self.local_addr.get_channel()
        logger.info(f"Creating local channel: {self.local_addr.get_string_channel()}")
        self.dht_interface = DHTClient(channel, self.my_addr)
        self.task_interface: TaskPeer = TaskPeer(channel, self.my_addr)
        # self.peer_interface: dict[StarAddress, PeerClient] = {}

    async def get_peer_transport(self, addr: bytes):
        # Peer ID. Get StarAddress
        tp_b = await self.dht_get(addr, DHTSelect.PEER_ID)
        if tp_b is None:
            return None
        tp = StarAddress.from_bytes(tp_b)
        return tp

    async def add_peer(self, addr: bytes, tp: StarAddress):
        await self.dht_set(addr, tp.to_bytes(), DHTSelect.PEER_ID)

    async def update_peers_seen(self, addr_list: set[bytes]):
        pass

    async def dispatch_event(self, evt: Event):
        # Sends to local.
        await self.task_interface.SendEvent(evt)

    def receive_event(self, evt):
        self.engine.recv_event(evt)

    async def get_task_owner(self, task: StarTask):
        # logger.debug("Get task table")
        # self.task_table.fancy_print()
        # await asyncio.sleep(10)

        out = await self.dht_get(task.get_id(), DHTSelect.TASK_ID)
        if out is None:
            logger.error(f"Owner for task {task.get_id().hex()} not found!")
            return b""
        tv = TaskValue.FromString(out)
        return tv.address

    def send_task_to_engine(self, task_b):
        obj = TaskValue.FromString(task_b)
        task = StarTask.from_bytes(obj.task_data)
        assert task.get_callable() != b""

        self.engine.import_task(task)

    async def allocate_task(self, task: StarTask):
        assert task.get_callable() != b""
        tv = TaskValue()
        tv.address = self.my_addr
        tv.task_data = task.to_bytes_with_callable()
        value = tv.SerializeToString()
        await self.dht_set(task.get_id(), value, DHTSelect.TASK_ID)

    async def dht_get(self, key: bytes, select: DHTSelect):

        # I don't have it.

        # It tries my local loopback.... interface is on local loopback.
        value, status, select_in = await self.dht_interface.FetchItem(
            key, select
        )  # send out.
        if status != DHTStatus.FOUND and status != DHTStatus.OWNED:
            return None

        assert select_in == select
        return value

    def dht_get_plain(self, key: bytes, select: DHTSelect):
        if select == DHTSelect.PEER_ID:
            response = self.peer_table.get(key)
        elif select == DHTSelect.TASK_ID:
            response = self.task_table.get(key)
        else:
            logger.error("Unknown table selected!")
            return
        return response.data, response.response_code, response.neighbor_addrs

    async def dht_set(self, key: bytes, value: bytes, select: DHTSelect):
        # It tries my local loopback.... interface is on local loopback.
        status = await self.dht_interface.StoreItem(key, value, select)  # send out.
        return status
        # Store on all transports!

    def dht_cache_store(self, key: bytes, value: bytes, select: DHTSelect):
        if select == DHTSelect.PEER_ID:
            self.peer_table.update_addresses(key)
            self.peer_table.set_cache(key, value)
            self.task_table.update_addresses(key)
        elif select == DHTSelect.TASK_ID:
            tv = TaskValue.FromString(value)
            tv.task_data = b""
            value = tv.SerializeToString()
            self.task_table.set_cache(key, value)
        else:
            logger.error("Unknown table selected!")

    async def dht_set_plain(self, key: bytes, value: bytes, select: DHTSelect):
        if select == DHTSelect.PEER_ID:
            self.peer_table.update_addresses(key)
            self.task_table.update_addresses(key)
            r = self.peer_table.set(key, value)
        elif select == DHTSelect.TASK_ID:
            # Do not post to cache for Task Alloc.
            # Put your address in the owner field!
            tsk = TaskValue.FromString(value)
            tv = TaskValue(address=self.my_addr, task_data=tsk.task_data)
            r = self.task_table.set(key, tv.SerializeToString(), post_to_cache=False)
            if r.response_code == DHTStatus.OWNED:
                self.send_task_to_engine(value)
        else:
            logger.error("Unknown table selected!")
            return

        return r.data, r.response_code, r.neighbor_addrs


#             RPC              RPC
# task_create --> task_allocate --> dht_store
