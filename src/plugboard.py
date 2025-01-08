"""
Plugboard.py

Serves as the middleware between the message services, DHTs, and internal Node APIs.
It's the low-level side while `node.py` is the high level that has the Node class that 
the outside world interacts with.
"""

import asyncio
import os
from typing import Optional

from src.KeepAlive import KeepAlive_Management, TRIGGER_OFFLINE
from src.communications.PeerService import PeerDiscoveryClient
from src.util.util import gaussian_bytes
from .core.star_engine import NodeEngine
from .core.DHT import *
from .communications.TaskService import TaskPeer
from .communications.DHTService import DHTClient
from .communications.main_pb2 import DHTSelect, DHTStatus
from .communications.primitives_pb2 import TaskValue
from .core.star_components import StarTask, StarProcess, StarAddress, Event
import logging

logger = logging.getLogger(__name__)


class PlugBoard:
    """Plugboard is a internal middleware class connecting the external Node API
    to the Messaging services, DHT, and other components.
    """

    def __init__(self, node_id: bytes, local_addr: StarAddress):
        """Create the middleware manager: Plugboard

        Args:
            node_id (bytes): Node ID
            local_addr (StarAddress): IP/Transport Address of the Node
        """
        self.my_addr = node_id
        self.engine = NodeEngine(node_id)
        self.engine.send_event_handler = self.dispatch_event

        self.keep_alive_manager = KeepAlive_Management()
        self.local_addr.set_keep_alive(self.keep_alive_manager)

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
        self.peer_discovery_interface = PeerDiscoveryClient(
            self.my_addr, self.local_addr
        )
        self.seen_peers: set[bytes] = set()
        self.received_rpcs = asyncio.Event()

    async def get_peer_transport(self, addr: bytes) -> Optional[StarAddress]:
        """Use the DHT to get transport address given Node ID

        Args:
            addr (bytes): Node ID to query

        Returns:
            Optional[StarAddress]: StarAddress of peer or None if not found.
        """
        # Peer ID. Get StarAddress
        tp_b = await self.dht_get(addr, DHTSelect.PEER_ID)
        if tp_b is None:
            return None
        # logger.debug(f"TP: {tp_b.hex()} - {tp_b}")
        tp = StarAddress.from_bytes(tp_b)
        tp.set_keep_alive(self.keep_alive_manager)
        return tp

    async def add_peer(self, addr: bytes, tp: StarAddress):
        """Add a peer node to the DHT

        Args:
            addr (bytes): Node ID
            tp (StarAddress): Transport Address
        """
        owners, who = await self.dht_set(addr, tp.to_bytes(), DHTSelect.PEER_ID)
        if addr != self.my_addr:
            return
        # Track owners.
        # who! currently just one owner. TODO.
        tp = await self.get_peer_transport(who)
        tp.set_keep_alive(self.keep_alive_manager)
        channel = tp.get_channel()
        self.keep_alive_manager.register_channel_service(
            channel, self.peer_self_cb_offline, TRIGGER_OFFLINE
        )

    async def peer_self_cb_offline(
        self,
    ):  # check if store peer is still storing my address
        pass

    async def peer_maintain_valid(self):  # store peer maintains connection to client
        pass

    async def peer_cache_maintain(self):  # cache. Listen for updates from owners.
        pass

    async def update_peers_seen(self, addr_list: set[bytes] | bytes):
        """A method for call by the message services marking a seen peer.

        Args:
            addr_list (set[bytes] | bytes): A set or a single Node ID seen.
        """
        self.received_rpcs.set()
        if isinstance(addr_list, set):
            for addr in addr_list:
                if self.peer_table.exists(addr):
                    continue
                self.seen_peers.add(addr)
            return
        self.seen_peers.add(addr_list)

    async def perform_discovery_round(self):
        """A single discovery round

        50% of the time search for a peer previously seen
        25% of the time search for a peer with a similar address to its own
        25% of the time search for a random peer

        """
        # Peers located somewhere in the network, but I may or may not know them. Add to cache.
        self.received_rpcs.clear()
        decision = random.random()
        if decision < 0.50:  # 50% of time, cache the viewed chains.
            peer_to_query = None
            for x in self.seen_peers:
                peer_to_query = x
                break
            if peer_to_query is None:
                return await self.perform_discovery_round()
            self.seen_peers.remove(peer_to_query)
            logger.info(
                f"Discovery: Searching for {peer_to_query.hex()} - chain - length remain: {len(self.seen_peers)}"
            )
            await self.get_peer_transport(peer_to_query)
            return
        if (
            decision < 0.75
        ):  # 25% of time, try to find new CLOSE people (use gauss dist)
            query = gaussian_bytes(self.my_addr[0:4], 2**16, 4)  # d route
            query = query + os.urandom(4)
            logger.info(
                f"Discovery: Searching for {query.hex()} - gauss - length remain: {len(self.seen_peers)}"
            )
            await self.get_peer_transport(query)
            return
        else:
            # 25% of time, try to find FAR people. (General random dist.)
            query = os.urandom(8)
            logger.info(
                f"Discovery: Searching for {query.hex()} - rand - length remain: {len(self.seen_peers)}"
            )
            await self.get_peer_transport(query)
            return

    async def perform_bootstrap(self, peer_addr: bytes, address: StarAddress):
        """Perform a bootstrap request.

        After sending out the bootstrap request to the target peer, update personal DHT cache

        Args:
            peer_addr (bytes): PeerID to reach out to
            address (StarAddress): Transport Address of peer to bootstrap
        """
        address.set_keep_alive(self.keep_alive_manager)
        peers = await self.peer_discovery_interface.Bootstrap(peer_addr, address)
        for peer in peers:
            peerID = peer.peer_id
            addr = StarAddress.from_pb(peer.addr)
            self.dht_cache_store(peerID, addr.to_bytes(), DHTSelect.PEER_ID)

    async def dispatch_event(self, evt: Event):
        """Dispatch an event to either the local engine or to the network

        Args:
            evt (Event): Event to dispatch
        """
        # Sends to local.
        status = await self.task_interface.SendEvent(evt)
        if status == DHTStatus.NOT_FOUND:
            logger.error("Unable to deliver event to node!")

    def receive_event(self, evt: Event):
        """For messaging service use. Send an event to personal engine

        Args:
            evt (Event): The event to send
        """
        self.engine.recv_event(evt)

    async def get_task_owner(self, task: StarTask) -> bytes:
        """Get the owner of a task (the peerID that the task is being run on)

        Args:
            task (StarTask): Task to query

        Returns:
            bytes: Peer ID of the owner
        """

        out = await self.dht_get(task.get_id(), DHTSelect.TASK_ID)
        if out is None:
            logger.error(f"Owner for task {task.get_id().hex()} not found!")
            return b""
        tv = TaskValue.FromString(out)
        return tv.address

    def send_task_to_engine(self, task_b: bytes):
        """Messaging Services API: Import a task for execution onto personal engine

        Args:
            task_b (bytes): TaskValue stored as bytes.
        """
        obj = TaskValue.FromString(task_b)
        task = StarTask.from_bytes(obj.task_data)
        assert task.get_callable() != b""

        self.engine.import_task(task)

    async def allocate_task(self, task: StarTask):
        """Node API: Allocate a task to the engine or to network

        Args:
            task (StarTask): Task to allocate
        """
        assert task.get_callable() != b""
        tv = TaskValue()
        tv.address = self.my_addr
        tv.task_data = task.to_bytes_with_callable()
        value = tv.SerializeToString()
        await self.dht_set(task.get_id(), value, DHTSelect.TASK_ID)

    async def dht_get(self, key: bytes, select: DHTSelect) -> Optional[bytes]:
        """Get a record from the DHT

        Args:
            key (bytes): Key
            select (DHTSelect): DHT to query

        Returns:
            Optional[bytes]: value or None for not found
        """
        # It tries my local loopback.... interface is on local loopback.
        value, status, select_in = await self.dht_interface.FetchItem(
            key, select
        )  # send out.
        if status != DHTStatus.FOUND and status != DHTStatus.OWNED:
            return None
        if value == b"":
            return None
        assert select_in == select
        return value

    def dht_get_plain(
        self, key: bytes, select: DHTSelect
    ) -> tuple[bytes, DHTStatus, list[bytes]]:
        """Messaging Services API: Fetch an item from local DHT

        Args:
            key (bytes): Key
            select (DHTSelect): DHT to query

        Returns:
            bytes: value
            DHTStatus: DHT response code
            list[bytes]: The peers last visited

            OR - returns NONE on error.
        """
        if select == DHTSelect.PEER_ID:
            response = self.peer_table.get(key)
        elif select == DHTSelect.TASK_ID:
            response = self.task_table.get(key)
        else:
            logger.error("Unknown table selected!")
            return  # type: ignore
        return response.data, response.response_code, response.neighbor_addrs

    async def dht_set(
        self, key: bytes, value: bytes, select: DHTSelect
    ) -> tuple[DHTStatus, bytes]:
        """Set value to DHT

        Args:
            key (bytes): key
            value (bytes): value
            select (DHTSelect): DHT to store on

        Returns:
            DHTStatus: Status of operation
        """

        status, who = await self.dht_interface.StoreItem(key, value, select)
        return status, who

    def dht_cache_store(self, key: bytes, value: bytes, select: DHTSelect):
        """Messaging Services: Store item in DHT cache

        Args:
            key (bytes): Key to store
            value (bytes): Value to store in cache
            select (DHTSelect): DHT to store under
        """
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

    async def dht_set_plain(
        self, key: bytes, value: bytes, select: DHTSelect, last_chain: bytes
    ) -> tuple[bytes, DHTStatus, list[bytes]]:
        """Messaging services: Store item in internal DHT

        Args:
            key (bytes): Key to store under
            value (bytes): The value to store
            select (DHTSelect): DHT table to store

        Returns:
            bytes: value
            DHTStatus: Status
            list[bytes]: neighbor addresses
        """
        if select == DHTSelect.PEER_ID:
            self.peer_table.update_addresses(key)
            self.task_table.update_addresses(key)
            r = self.peer_table.set(key, value)
            if r.response_code == DHTStatus.OWNED:
                # I own now. Add callback to KeepAlive
                addr = StarAddress.from_bytes(value)
                addr.set_keep_alive(self.keep_alive_manager)
                channel = addr.get_channel()
                self.keep_alive_manager.register_channel_service(
                    channel, self.peer_maintain_valid, TRIGGER_OFFLINE
                )
            elif r.response_code == DHTStatus.FOUND:
                # cache.
                addr = StarAddress.from_bytes(value)
                addr.set_keep_alive(self.keep_alive_manager)
                channel = addr.get_channel()
                self.keep_alive_manager.register_channel_service(
                    channel, self.peer_cache_maintain, TRIGGER_OFFLINE
                )

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
            return  # type: ignore

        return r.data, r.response_code, r.neighbor_addrs


#             RPC              RPC
# task_create --> task_allocate --> dht_store
