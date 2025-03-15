"""
Plugboard.py

Serves as the middleware between the message services, DHTs, and internal Node APIs.
It's the low-level side while `node.py` is the high level that has the Node class that
the outside world interacts with.
"""

import asyncio
import os
import random
from typing import Optional

import grpc

from src.KeepAlive import KeepAlive_Management, TRIGGER_OFFLINE
from src.TaskMonitor import MonitorService
from src.communications.FileService import FileClient
from src.communications.IOService import IOClient
from src.communications.PeerService import PeerDiscoveryClient
from src.core.File import HostedFile, FileManager
from src.core.io_host import IO_BUSY, IO_DETACHED, IO_NONEXIST, IO_OK, Device, IOHost
from src.util.util import gaussian_bytes
from .core.star_engine import NodeEngine
from .core.DHT import *
from .communications.TaskService import TaskPeer
from .communications.DHTService import DHTClient
from .communications.main_pb2 import DHTSelect, DHTStatus, FileValue
from .communications.primitives_pb2 import TaskValue
from .core.star_components import StarTask, StarProcess, StarAddress, Event
import logging
import src.util.sim_log as sim

logger = logging.getLogger(__name__)


def convert_io_status(status):
    if status == IO_OK:
        return DHTStatus.OK
    elif status == IO_BUSY:
        return DHTStatus.FOUND
    elif status == IO_DETACHED:
        return DHTStatus.ERR
    return DHTStatus.ERR


def convert_to_io_status(status):
    if status == DHTStatus.OK:
        return IO_OK
    if status == DHTStatus.FOUND:
        return IO_BUSY
    if status == DHTStatus.ERR:
        return IO_DETACHED
    return IO_NONEXIST


class PlugBoard:
    """Plugboard is a internal middleware class connecting the external Node API
    to the Messaging services, DHT, and other components.
    """

    def __init__(self, node_id: bytes, local_addr: StarAddress, file_save: str, node):
        """Create the middleware manager: Plugboard

        Args:
            node_id (bytes): Node ID
            local_addr (StarAddress): IP/Transport Address of the Node
        """
        self.my_addr = node_id
        self.engine = NodeEngine(node_id)
        self.engine.send_event_handler = self.dispatch_event
        # security warning: tasks can access kernel
        self.engine.plugboard_internal = self

        self.keep_alive_manager = KeepAlive_Management(node_id, self.general_offline_cb)
        self.local_addr = local_addr
        self.local_addr.set_keep_alive(self.keep_alive_manager)

        self.peer_table = DHT(self.my_addr)
        self.peer_table.update_addresses(node_id)
        self.peer_table.set(node_id, local_addr.to_bytes())
        self.cache_subscriptions_serve: dict[DHTSelect, dict[bytes, set[bytes]]] = {
            DHTSelect.PEER_ID: {self.my_addr: set()},
            DHTSelect.TASK_ID: {self.my_addr: set()},
            DHTSelect.FILE_ID: {self.my_addr: set()},
            DHTSelect.DEVICE_ID: {self.my_addr: set()},
        }  # stores KEY and peers caching.

        self.cache_subscriptions: dict[DHTSelect, set[bytes]] = {
            DHTSelect.PEER_ID: set(),
            DHTSelect.TASK_ID: set(),
            DHTSelect.FILE_ID: set(),
            DHTSelect.DEVICE_ID: set(),
        }

        self.task_table = DHT(self.my_addr)
        self.task_table.update_addresses(node_id)

        self.file_table = DHT(self.my_addr)
        self.file_table.update_addresses(node_id)

        self.device_table = DHT(self.my_addr)
        self.device_table.update_addresses(node_id)

        logger.info(
            f"META - Creating local channel: {self.local_addr.get_string_channel()}"
        )
        self.dht_interface = DHTClient(
            self.local_addr, self.my_addr, self.my_addr, self.keep_alive_manager
        )
        self.task_interface: TaskPeer = TaskPeer(self.local_addr, self.my_addr)
        self.peer_discovery_interface = PeerDiscoveryClient(
            self.my_addr, self.local_addr
        )
        self.seen_peers: set[bytes] = set()
        self.received_rpcs = asyncio.Event()
        self.monitor_service = MonitorService()

        # Task ID --> Peer ID (Monitor)
        self.monitor_servers: dict[bytes, bytes] = {}
        # # File ID --> Peer ID (Monitor)
        # self.file_monitor_servers: dict[bytes, bytes] = {}

        self.file_manager = FileManager(file_save)
        self.io_host = IOHost(self.my_addr)  # all devices join here.
        self.io_host.host_alloc_device = self.host_allocate_device  # type: ignore
        self.io_host.host_dealloc_device = self.host_deallocate_device  # type: ignore
        self.node_object = node

    def print_keep_alives(self):
        self.keep_alive_manager.fancy_print()

    def print_task_table(self):
        self.task_table.fancy_print()

    def print_cache_subscriptions_serve(self):
        for select in self.cache_subscriptions_serve:
            if select != DHTSelect.PEER_ID:
                continue
            for key in self.cache_subscriptions_serve[select]:
                for host in self.cache_subscriptions_serve[select][key]:
                    logger.info(
                        f"PEER - PEER_TABLE \t [{key.hex()}] --forward--> {host.hex()}"
                    )

    def print_cache_subscriptions_listening(self):
        for select in self.cache_subscriptions:
            if select == DHTSelect.PEER_ID:
                for key in self.cache_subscriptions[select]:
                    logger.info(f"PEER - PEER_TABLE \t [{key.hex()}]")
            if select == DHTSelect.TASK_ID:
                for key in self.cache_subscriptions[select]:
                    logger.info(f"TASK - TASK_TABLE \t [{key.hex()}]")
            if select == DHTSelect.FILE_ID:
                for key in self.cache_subscriptions[select]:
                    logger.info(f"FILE - FILE_TABLE \t [{key.hex()}]")
            if select == DHTSelect.DEVICE_ID:
                for key in self.cache_subscriptions[select]:
                    logger.info(f"IO - DEVICE_TABLE \t [{key.hex()}]")

    def remove_peer_from_address_tables(self, peer):
        log = sim.SimLogger()
        log.log(sim.LOG_DHT_ADDRESS_DELETE, self.my_addr, peer)
        self.peer_table.remove_address(peer)
        self.task_table.remove_address(peer)
        self.file_table.remove_address(peer)
        self.device_table.remove_address(peer)

    async def get_peer_transport(self, addr: bytes, ignore=[]) -> Optional[StarAddress]:
        """Use the DHT to get transport address given Node ID

        Args:
            addr (bytes): Node ID to query

        Returns:
            Optional[StarAddress]: StarAddress of peer or None if not found.
        """
        logger.debug(f"PEER - GET PEER TRANSPORT {addr.hex()}")
        # Peer ID. Get StarAddress
        tp_b = await self.dht_get(addr, DHTSelect.PEER_ID, ignore=ignore)
        if tp_b is None:
            logger.debug("PEER - DONE PEER TRANSPORT NONE")
            return None
        # logger.debug(f"TP: {tp_b.hex()} - {tp_b}")
        tp = StarAddress.from_bytes(tp_b)
        tp.set_keep_alive(self.keep_alive_manager)
        logger.debug(
            f"PEER - DONE PEER TRANSPORT {addr.hex()} --> {tp.get_string_channel()}"
        )
        return tp

    async def add_peer(self, addr: bytes, tp: StarAddress):
        """Add a peer node to the DHT

        Args:
            addr (bytes): Node ID
            tp (StarAddress): Transport Address
        """
        logger.debug(f"PEER - Add peer {addr.hex()} at {tp.get_string_channel()}")
        owners, who = await self.dht_set(addr, tp.to_bytes(), DHTSelect.PEER_ID)
        # logger.debug(f"Add peer done")
        if addr != self.my_addr:
            return
        # Track owners.
        # who! currently just one owner. TODO.
        logger.debug(f"PEER - Creating listener to storer of my address - {who.hex()}")
        tp = await self.get_peer_transport(who)  # type: ignore
        assert tp is not None
        tp.set_keep_alive(self.keep_alive_manager)
        channel = tp.get_channel()
        if tp.get_string_channel() == self.local_addr.get_string_channel():
            logger.debug(
                "PEER - Not creating listener to storer of my address as it's me!"
            )
            return
        self.keep_alive_manager.register_channel_service(
            channel,
            tp.get_string_channel(),
            addr,
            lambda: self.peer_self_cb_offline(addr),
            TRIGGER_OFFLINE,
        )

    async def peer_self_cb_offline(
        self, peer_id: Optional[bytes]
    ):  # check if store peer is still storing my address
        # peer is no longer storing the address!
        if peer_id is None:
            logger.error("PEER - Self CB peer ID None!")
            return

        logger.info(
            f"PEER - Owner of my transport address {self.my_addr.hex()} went offline. Resending"
        )

        # store-er went offline! Resend address.
        self.remove_peer_from_address_tables(peer_id)
        await self.add_peer(self.my_addr, self.local_addr)

    async def peer_maintain_valid_offline(self, peer_id: Optional[bytes]):
        # peer_id went offline. I own the peer's address. Delete
        if peer_id is None:
            logger.error("PEER - Maintain CB can't be None!")
            return

        await self.dht_delete_plain(peer_id, DHTSelect.PEER_ID)

    async def device_maintain_valid_offline(self, device_key, peer_id):
        if peer_id is None:
            logger.error("IO - Maintain CB can't be None!")
            return

        await self.dht_delete_plain(device_key, DHTSelect.DEVICE_ID)

    async def send_deletion_notice(self, key, select):
        tmp = set()

        logger.warning("PEER - Final subscriptions serving  - delete")
        self.print_cache_subscriptions_serve()
        logger.debug(f"PEER - {self.cache_subscriptions_serve}")
        logger.debug(f"PEER - {self.cache_subscriptions_serve[select][key]}")
        logger.debug(f"PEER - {select}")
        logger.debug(f"PEER - {key}")

        cp = self.cache_subscriptions_serve[select][key].copy()
        for cacher in cp:
            logger.debug(f"PEER - {cacher.hex()}")

            tp = await self.get_peer_transport(cacher)
            if tp is not None:  # peer already deleted!
                cli = DHTClient(tp, cacher, self.my_addr, self.keep_alive_manager)
                await cli.send_deletion_notice(key, select)  # tell cachers offline!
            tmp.add(cacher)

        for cacher in tmp:
            self.cache_subscriptions_serve[select][key].remove(cacher)

    async def peer_cache_maintain_offline(
        self, peer_id: bytes, key: bytes
    ):  # cache. Listen for owner / prev chain to go down.
        """A

        Args:
            peer_id (bytes): Monitor chain
            key (bytes): Key of data
        """

        self.remove_peer_from_address_tables(peer_id)
        tp: StarAddress | None = await self.get_peer_transport(key)
        if tp is None:
            await self.dht_delete_plain(peer_id, DHTSelect.PEER_ID)
            # await self.send_deletion_notice(peer_id, DHTSelect.PEER_ID)
            return
        kp = self.keep_alive_manager.get_kp_channel(tp, key)
        exists = await kp.verify()
        if not (exists):
            # offline!
            await self.dht_delete_plain(peer_id, DHTSelect.PEER_ID)
            # await self.send_deletion_notice(peer_id, DHTSelect.PEER_ID)
            return

        # online!
        await self.add_peer(key, tp)

    def get_kp_man(self) -> KeepAlive_Management:
        return self.keep_alive_manager

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
                return  # await self.perform_discovery_round()
            self.seen_peers.remove(peer_to_query)
            logger.info(
                f"DISCOVERY - Discovery: Searching for {peer_to_query.hex()} - chain - length remain: {len(self.seen_peers)}"
            )
            await self.get_peer_transport(peer_to_query)
            return
        # if (
        #     decision < 0.75
        # ):  # 25% of time, try to find new CLOSE people (use gauss dist)
        #     query = gaussian_bytes(self.my_addr[0:4], 2**16, 4)  # d route
        #     query = query + os.urandom(4)
        #     logger.info(
        #         f"DISCOVERY - Discovery: Searching for {query.hex()} - gauss - length remain: {len(self.seen_peers)}"
        #     )
        #     await self.get_peer_transport(query)
        #     return

        # else:
        # 50% of time, try to find FAR people. (General random dist.)
        query = os.urandom(8)
        logger.info(
            f"DISCOVERY - Discovery: Searching for {query.hex()} - rand - length remain: {len(self.seen_peers)}"
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
        logger.debug("DISCOVERY - PERFORM BOOTSTRAP")
        address.set_keep_alive(self.keep_alive_manager)
        peers = await self.peer_discovery_interface.Bootstrap(peer_addr, address)
        for peer in peers:
            peerID = peer.peer_id
            addr = StarAddress.from_pb(peer.addr)
            logger.debug(f"DHT Cache Store [{peerID.hex()}] monitor: {peer_addr.hex()}")
            await self.dht_cache_store(
                peerID, addr.to_bytes(), DHTSelect.PEER_ID, peer_addr
            )

        # send out my address given the new info.
        logger.debug("DISCOVERY - Sending out my address...")
        await self.add_peer(self.my_addr, self.local_addr)
        logger.debug("DISCOVERY - PERFORM BOOTSTRAP DONE")

    async def dispatch_event(self, evt: Event):
        """Dispatch an event to either the local engine or to the network

        Args:
            evt (Event): Event to dispatch
        """
        logger.info(f"TASK - Dispatch event to task: {evt.target.get_id().hex()}")
        logger.debug(f"TASK - {evt}")
        logger.debug(f"TASK - {evt.is_checkpoint}")
        logger.debug(f"TASK - {evt.origin}")
        assert str(evt).find("Event object") != -1
        # Sends to local.

        slog = sim.SimLogger()
        session = slog.start_session()
        slog.log(
            sim.LOG_PROCESS_EVENT_SEND,
            self.my_addr,
            self.my_addr,
            session=session,
            contentID=evt.target.get_id(),
        )

        try:
            resp = await self.task_interface.SendEvent(evt, simulation_session=session)
        except:
            logger.info("Unable to deliver event to node!")
            return False

        if resp.status == DHTStatus.NOT_FOUND:
            logger.info("Unable to deliver event to node!")
            return False

        logger.info(f"TASK - Dispatch event DONE!")
        return True
        # if resp.remaining == 0:
        #     # send out!
        #     # There is already an owner, so one is fine.
        #     await self.send_out_single_task(proc, evt.target, ignore=[resp.who])
        # else:
        #     logger.debug(
        #         f"Dispatched event complete: Remaining units: {resp.remaining}"
        #     )

    def receive_event(self, evt: Event):
        """For messaging service use. Send an event to personal engine

        Args:
            evt (Event): The event to send
        """
        return self.engine.recv_event(evt)

    async def get_task_owner(self, task: StarTask) -> bytes:
        """Get the owner of a task (the peerID that the task is being run on)

        Args:
            task (StarTask): Task to query

        Returns:
            bytes: Peer ID of the owner
        """

        out = await self.dht_get(task.get_id(), DHTSelect.TASK_ID)
        if out is None:
            logger.warning(f"TASK - Owner for task {task.get_id().hex()} not found!")
            return b""
        tv = TaskValue.FromString(out)
        return tv.address

    async def send_task_to_engine(self, task_b: bytes):
        """Messaging Services API: Import a task for execution onto personal engine

        Args:
            task_b (bytes): TaskValue stored as bytes.
        """

        obj = TaskValue.FromString(task_b)
        task = StarTask.from_bytes(obj.task_data)
        logger.info(f"TASK - Stored Task! {task.get_id().hex()}")
        self.task_table.fancy_print()
        proc = StarProcess.from_bytes(obj.process_data)
        assert task.get_callable() != b""

        # Require a Monitor!
        monitor_peer = await self.create_monitor_request(proc, task)
        task.monitor = monitor_peer  # check: What if this monitor changes???
        self.engine.import_task(task, proc)

    async def create_monitor_request(
        self, proc: StarProcess, task: StarTask, monitor_peer_old: bytes = b""
    ):
        logger.info(f"TASK - Trying to get a monitor for task {task.get_id().hex()}")
        assert task.get_callable() != b""
        # On monitor fail, pick a new monitor

        # Pick a random node (later adjust to be one that is close.)
        # Don't pick where it came from or myself
        ignore = set([self.my_addr, monitor_peer_old])
        while True:
            monitor_peer = self.peer_table.get_next_closest_neighbor(
                self.my_addr, ignore=ignore
            )

            if monitor_peer is None:
                logger.error(
                    f"TASK - There are no other peers send to monitor! You need more peers! Operating solo!"
                )
                return

            tp: StarAddress | None = await self.get_peer_transport(monitor_peer)

            # double check that peer is online!
            assert tp is not None
            b = await self.keep_alive_manager.test(tp, monitor_peer)
            logger.debug(f"TASK - {b}")
            if b:
                break
            ignore.add(monitor_peer)

        logger.info(
            f"TASK - Send monitor request {task.get_id().hex()} to {monitor_peer}"
        )
        assert tp is not None
        task_peer = TaskPeer(tp, monitor_peer)
        await task_peer.SendMonitor_Request(proc, self.my_addr, task)  # have monitor!

        self.monitor_servers[task.get_id()] = monitor_peer

        async def tmp():
            self.remove_peer_from_address_tables(monitor_peer)
            await self.create_monitor_request(proc, task, monitor_peer)

        kp_channel = self.keep_alive_manager.register_channel_service(
            tp.get_channel(),
            tp.get_string_channel(),
            monitor_peer,
            tmp,
            TRIGGER_OFFLINE,
        )
        await kp_channel.update()
        self.engine.update_monitor(task, monitor_peer)
        return monitor_peer

    async def create_file_monitor_request(
        self, file: HostedFile, monitor_peer_old: bytes = b""
    ):
        logger.info(f"FILE - Trying to get a monitor for file {file.get_key().hex()}")

        # On monitor fail, pick a new monitor

        # Pick the NEXT CLOSEST node (later adjust to be one that is close.)
        # Don't pick where it came from or myself
        ignore = set([self.my_addr, monitor_peer_old])
        while True:
            monitor_peer = self.peer_table.get_next_closest_neighbor(
                file.get_key(), ignore
            )

            if monitor_peer is None:
                logger.error(
                    f"FILE - There are no other peers send to monitor! You need more peers! Operating solo!"
                )
                return

            tp: StarAddress | None = await self.get_peer_transport(monitor_peer)

            # double check that peer is online!
            assert tp is not None
            b = await self.keep_alive_manager.test(tp, monitor_peer)
            logger.debug(f"FILE - {b}")
            if b:
                break
            ignore.add(monitor_peer)

        assert tp is not None
        file_peer = FileClient(
            tp, monitor_peer, b"", is_monitor=True
        )  # unknown process ID.
        contents = self.file_manager.fetch_contents(
            file, is_monitor=False
        )  # I own, so not is_monitor

        if contents is None:
            contents = b""

        logger.info(
            f"FILE - Send monitor request {file.get_key().hex()} to {monitor_peer.hex()} {contents}"
        )
        await file_peer.SendMonitorRequest(
            file, contents, self.my_addr
        )  # have monitor!

        # self.file_monitor_servers[file.get_key()] = monitor_peer

        async def tmp():
            logger.warning("FILE - Monitor offline for file! Respawning monitor.")
            self.remove_peer_from_address_tables(monitor_peer)
            await self.create_file_monitor_request(file, monitor_peer)

        kp_channel = self.keep_alive_manager.register_channel_service(
            tp.get_channel(),
            tp.get_string_channel(),
            monitor_peer,
            tmp,
            TRIGGER_OFFLINE,
        )
        await kp_channel.update()
        # update monitor in file manager
        self.file_manager.update_monitor(file, monitor_peer)
        logger.info("FILE - Done. Have Monitor for file!")
        return monitor_peer

    async def allocate_program(self, proc: StarProcess):
        """Node API: Allocate a task to the engine or to network

        Args:
            task (StarTask): Program to allocate
        """

        for task in proc.get_tasks():
            assert task.get_callable() != b""
            who = await self.send_out_single_task(proc, task)
            logger.info(f"TASK - WHO: {who.hex()}")
            # w2 = await self.send_out_single_task(
            #     proc, task, [who]
            # )  # require at least two different owners at all times!
            # logger.info(f"WHO2: {w2.hex()}")

    async def send_out_single_task(
        self, process: StarProcess, task: StarTask, ignore: list[bytes] = []
    ):
        tv = TaskValue()
        tv.address = self.my_addr  # replace with STORER
        tv.task_data = task.to_bytes_with_callable()
        tv.process_data = process.get_all_task_bytes()
        assert task.get_callable() != b""
        status, who = await self.dht_set(
            task.get_id(),
            tv.SerializeToString(),
            DHTSelect.TASK_ID,
            nodes_visited=ignore,
        )
        if status == DHTStatus.NOT_FOUND:
            logger.error(
                f"TASK - Can't store item! Maybe need to connect to more peers?"
            )
            return

        # Track owners.
        # who! currently just one owner. TODO.
        # logger.debug(f"Creating listener to storer of my task - {who.hex()}")
        # logger.debug(f"Who: {who.hex()}")
        # tp = await self.get_peer_transport(who, ignore=ignore)  # type: ignore
        # assert tp is not None
        # logger.debug(f"TP: {tp.get_string_channel()}")
        # tp.set_keep_alive(self.keep_alive_manager)
        # channel = tp.get_channel()
        # if tp.get_string_channel() == self.local_addr.get_string_channel():
        #     logger.debug("Not creating listener to storer of my address as it's me!")
        #     return self.my_addr
        # self.keep_alive_manager.register_channel_service(
        #     channel,
        #     tp.get_string_channel(),
        #     who,
        #     lambda: self.task_self_cb_offline(process, task, who),
        #     TRIGGER_OFFLINE,
        # )
        return who

    async def task_self_cb_offline(
        self, process: StarProcess, task: StarTask, who: bytes
    ):
        # Owner for task went offline. Respawn
        logger.info(f"TASK - Storer went offline for task: {task.get_id().hex()}")

        # Don't send anything anywhere. Have monitor do that.
        # who2 = await self.send_out_single_task(process, task, ignore=[who])
        # # require at least two different owners at all times!
        # await self.send_out_single_task(process, task, ignore=[who, who2])

    async def receive_monitor_request(
        self, proc: StarProcess, who: bytes, task: StarTask
    ):
        self.monitor_service.add_process(proc, who, task)
        # Add keepalive

        tp = await self.get_peer_transport(who)
        assert tp is not None
        assert task.get_callable() != b""
        self.keep_alive_manager.register_channel_service(
            tp.get_channel(),
            tp.get_string_channel(),
            who,
            lambda: self.process_owner_offline(
                proc,
                task,
                who,
            ),
            TRIGGER_OFFLINE,
        )

    async def receive_file_monitor_request(
        self, file: HostedFile, who: bytes, contents: bytes
    ):
        # host the file.
        # monitor_peer = await self.create_file_monitor_request(hf)
        self.file_manager.host_file(file, b"", is_monitor=True, contents=contents)

        tp = await self.get_peer_transport(who)
        assert tp is not None
        self.keep_alive_manager.register_channel_service(
            tp.get_channel(),
            tp.get_string_channel(),
            who,
            lambda: self.process_file_offline(
                file,
                who,
            ),
            TRIGGER_OFFLINE,
        )

    async def process_file_offline(self, file: HostedFile, who: bytes):
        # who is offline. Respawn file.
        # store file somewhere else.
        logger.warning(f"FILE - File owner offline! {file.get_key().hex()}")
        self.remove_peer_from_address_tables(who)
        contents = self.file_manager.fetch_contents(file, is_monitor=True)
        await self.dht_set(
            file.get_key(), self.my_addr, DHTSelect.FILE_ID, nodes_visited=[who]
        )
        peer = await self.dht_get(file.get_key(), DHTSelect.FILE_ID, ignore=[who])
        assert peer is not None
        tp = await self.get_peer_transport(peer)
        assert tp is not None

        # send file to tp.
        fc = FileClient(tp, peer, b"")
        await fc.SendFileContents(file, contents)
        # fc.close() # ?????

        # stop my monitoring....
        self.file_manager.remove_monitor(file)

        # stop my monitor of the file.

    async def process_owner_offline(
        self, proc: StarProcess, task: StarTask, who: bytes
    ):
        logger.info(f"TASK - CB OWNER OFFLINE of task: {task.get_id().hex()}")
        self.task_table.fancy_print()
        # Owner is offline!
        self.remove_peer_from_address_tables(who)
        await self.send_out_single_task(proc, task, ignore=[who, self.my_addr])
        evt = self.monitor_service.recall_most_recent_event(
            who, task.get_process_id(), task.get_id()
        )
        if evt is None:
            logger.warning(f"TASK - No event found. Skip")
            return

        async def delay_and_fire():
            for r in range(4):
                logger.warning(
                    f"TASK - CB OWNER OFFLINE Dispatch Resume Event! try: {r} {evt.target.get_id().hex()}"
                )
                result = await self.dispatch_event(evt)  # resume execution.
                # result = True
                if result:
                    return
                await asyncio.sleep(0.10)  # Wait for all tasks to be allocated
            logger.error(
                f"TASK - Unable to deliver event to node! {evt.target.get_id().hex()}"
            )

        asyncio.create_task(delay_and_fire())

        # Send out the task to someone else!

    async def receive_checkpoint(
        self,
        proc: bytes,
        who: bytes,
        event_origin: Event | None,
        event_to: Event,
        forwards=False,
    ):
        # called from server SendCheckpoint()

        if forwards:
            self.monitor_service.add_checkpoint(who, event_origin, event_to)
        else:
            if event_origin is None:
                return
            status = self.monitor_service.remove_checkpoint(who, event_origin, event_to)
            if not (status):
                logger.warning(
                    f"TASK - Checkpoint for {event_origin.target.get_id().hex()} not found in monitor!"
                )

    async def send_checkpoint_forward(
        self,
        task_id: bytes,
        event_origin: Event | None,
        event_target: Event,
    ):
        # Called from send_event()
        # Alert my monitor

        # tell the next person checkpoint.
        # await self.internal_callback.send_checkpoint_forward(
        #     task_to.get_id(), evt.origin, evt
        # )
        # # tell the previous person that we are good.
        # await self.internal_callback.send_checkpoint_backward(
        #     task_to.get_id(), evt.origin, evt.origin_previous, evt
        # )

        logger.debug(f"TASK - self.monitor_servers")
        if task_id not in self.monitor_servers:
            logger.error(f"TASK - No monitor found for process: {task_id.hex()}")
            return

        monitor_peer = self.monitor_servers[task_id]
        tp = await self.get_peer_transport(monitor_peer)
        assert tp is not None
        while True:
            test = await self.keep_alive_manager.test(tp, monitor_peer)
            if test:
                break
            while True:
                new_peer = self.monitor_servers[task_id]
                if monitor_peer != new_peer:
                    break
                await asyncio.sleep(0.02)  # wait for monitor to spawn
                logger.debug("TASK - Waiting for monitor...")
            monitor_peer = new_peer
            tp = await self.get_peer_transport(monitor_peer)
            assert tp is not None

        slog = sim.SimLogger()
        slog.log(
            sim.LOG_PROCESS_CHECKPOINT,
            self.my_addr,
            monitor_peer,
            contentID=task_id,
        )
        logger.info(f"TASK - Send checkpoint {monitor_peer.hex()}")
        taskClient = TaskPeer(tp, monitor_peer)
        await taskClient.SendCheckpoint(
            task_id, event_origin, event_target, self.my_addr
        )

    async def send_checkpoint_backward(
        self,
        task_id: bytes,
        event_origin: Event,
        event_origin_previous: Event | None,
        event_target: Event,
    ):
        # Tell event origin's monitor that it is done!
        if event_origin_previous is None or event_origin is None:
            return
        monitor_peer = event_origin_previous.target.monitor  # what if monitor dies??

        logger.info(f"TASK - Send checkpoint BACKWARD {monitor_peer.hex()}")
        if monitor_peer is None or monitor_peer == b"":
            return
        tp = await self.get_peer_transport(monitor_peer)
        if tp is None:
            logger.error(
                f"TASK - {monitor_peer} is unreachable! Do you need a bigger network?"
            )
            return
        assert tp is not None

        is_alive = await self.keep_alive_manager.test(tp, monitor_peer)

        if not (is_alive):
            return  # plugboard will later assign new monitor

        slog = sim.SimLogger()
        slog.log(
            sim.LOG_PROCESS_CHECKPOINT,
            self.my_addr,
            monitor_peer,
            contentID=task_id,
        )
        taskClient = TaskPeer(tp, monitor_peer)
        await taskClient.SendCheckpoint(
            task_id, event_origin_previous, event_origin, self.my_addr, backwards=True
        )

    async def file_create(self, file: HostedFile):
        await self.create_file(file)

    async def file_open(self, file: HostedFile, process_id: bytes):
        # get peer that it is being hosted on.
        peerID = await self.dht_get(file.get_key(), DHTSelect.FILE_ID)
        if peerID is None:
            return None
        addr = await self.get_peer_transport(peerID)
        assert addr is not None

        slog = sim.SimLogger()
        slog.log(
            sim.LOG_FILE_DATA_REQUEST,
            self.my_addr,
            peerID,
            contentID=file.get_key(),
            other="open",
        )

        fc = FileClient(addr, peerID, process_id)
        identifier = await fc.OpenFile(file)
        file.local_identifier = identifier
        return file

    async def file_read(self, file: HostedFile, process_id: bytes, length: int):
        # get peer that it is being hosted on.
        peerID = await self.dht_get(file.get_key(), DHTSelect.FILE_ID)
        assert peerID is not None
        addr = await self.get_peer_transport(peerID)
        assert addr is not None

        slog = sim.SimLogger()
        slog.log(
            sim.LOG_FILE_DATA_REQUEST,
            self.my_addr,
            peerID,
            contentID=file.get_key(),
            other="read",
        )

        fc = FileClient(addr, peerID, process_id)
        data = await fc.ReadFile(file, length)
        return data

    async def file_write(self, file: HostedFile, process_id: bytes, data: bytes):
        # get peer that it is being hosted on.
        peerID = await self.dht_get(file.get_key(), DHTSelect.FILE_ID)
        assert peerID is not None
        addr = await self.get_peer_transport(peerID)
        assert addr is not None

        slog = sim.SimLogger()
        slog.log(
            sim.LOG_FILE_DATA_REQUEST,
            self.my_addr,
            peerID,
            contentID=file.get_key(),
            other="write",
        )

        fc = FileClient(addr, peerID, process_id)
        data = await fc.WriteFile(file, data)
        return data

    async def file_seek(
        self, file: HostedFile, process_id: bytes, offset: int, whence: int
    ):
        # get peer that it is being hosted on.
        peerID = await self.dht_get(file.get_key(), DHTSelect.FILE_ID)
        assert peerID is not None
        addr = await self.get_peer_transport(peerID)
        assert addr is not None

        slog = sim.SimLogger()
        slog.log(
            sim.LOG_FILE_DATA_REQUEST,
            self.my_addr,
            peerID,
            contentID=file.get_key(),
            other="seek",
        )

        fc = FileClient(addr, peerID, process_id)
        data = await fc.SeekFile(file, offset, whence)
        return data

    async def file_close(self, file: HostedFile, process_id: bytes):
        # get peer that it is being hosted on.
        peerID = await self.dht_get(file.get_key(), DHTSelect.FILE_ID)
        assert peerID is not None
        addr = await self.get_peer_transport(peerID)
        assert addr is not None

        slog = sim.SimLogger()
        slog.log(
            sim.LOG_FILE_DATA_REQUEST,
            self.my_addr,
            peerID,
            contentID=file.get_key(),
            other="close",
        )

        fc = FileClient(addr, peerID, process_id)
        data = await fc.CloseFile(file)
        return data

    async def fetch_file(
        self,
        key: bytes,
        local_file_identifier: bytes,
        process_id: bytes = b"",
        direct_access=False,
        is_monitor=False,
    ):
        if not (self.file_manager.is_file_hosted(key, is_monitor)):
            raise ValueError("Not Found!")

        file, monitor = self.file_manager.fetch_file(
            key,
            local_file_identifier,
            process_id,
            direct_access,
            is_monitor=is_monitor,
        )

        return file, monitor

    def close_file(self, key: bytes, local_identifier: bytes, is_monitor=False):
        if not (self.file_manager.is_file_hosted(key, is_monitor=is_monitor)):
            raise ValueError("Not Found!")

        self.file_manager.close_file(key, local_identifier, is_monitor)
        return

    # async def open_file(self, key: bytes, process_id: bytes, is_monitor=False):
    #     if not (self.file_manager.is_file_hosted(key, is_monitor)):
    #         raise ValueError("Not Found!")

    #     file = self.file_manager.fetch_file(
    #         key, local_file_identifier=b"", process_id=process_id, is_monitor=is_monitor
    #     )
    #     return file

    async def create_file(self, hf: HostedFile):
        # It sets the value later.... (under raw store)
        await self.dht_set(hf.get_key(), b"", DHTSelect.FILE_ID)

    async def host_allocate_device(self, dev: Device):
        # Assume teletype device
        logger.info(f"Allocating device {dev.get_name()}")
        await self.dht_set(
            dev.get_id(), self.my_addr, DHTSelect.DEVICE_ID, fixed_owner=True
        )

    async def host_deallocate_device(self, dev: Device):
        logger.info(f"IO - Device dealloced! {dev.get_name()}")
        await self.dht_delete_plain(dev.get_id(), DHTSelect.DEVICE_ID)

    async def open_device(self, device, process_id):
        local_id, status = self.io_host.open_device_connection(device, process_id)
        status = convert_io_status(status)
        return local_id, status

    async def close_device(self, device):
        status = self.io_host.close_device(device)
        return convert_io_status(status)

    async def unmount_device(self, device):
        await self.io_host.unmount_device(device)
        return DHTStatus.OK

    async def read_device(self, device: Device, length: int):
        r, status = await self.io_host.read_device(device, length)
        return r, convert_io_status(status)

    async def write_device(self, device, data):
        status = await self.io_host.write_device(device, data)
        return convert_io_status(status)

    async def read_available(self, device):
        r, s = await self.io_host.read_available(device)
        return r, convert_io_status(s)

    async def write_handler(self, device: Device, data):
        # search for device.
        # send request to device.
        logger.info(f"IO - Write request")
        who = await self.dht_get(device.get_id(), DHTSelect.DEVICE_ID)
        if who is None:
            return IO_NONEXIST
        tp = await self.get_peer_transport(who)
        if tp is None:
            return IO_NONEXIST
        idf = device.get_local_device_identifier()
        if idf is None:
            return IO_BUSY

        slog = sim.SimLogger()
        slog.log(
            sim.LOG_IO_REQUEST,
            self.my_addr,
            who,
            contentID=device.get_id(),
            other="write",
        )
        ioc = IOClient(tp, who, idf)
        status = await ioc.WriteDevice(device, data)
        status = convert_to_io_status(status)
        logger.info(f"IO - Write request done")
        return status

    async def read_handler(self, device: Device, l):
        # search for device.
        # send request to device.
        who = await self.dht_get(device.get_id(), DHTSelect.DEVICE_ID)
        if who is None:
            return b"", IO_NONEXIST
        tp = await self.get_peer_transport(who)
        if tp is None:
            return b"", IO_NONEXIST
        idf = device.get_local_device_identifier()
        if idf is None:
            return b"", IO_BUSY
        slog = sim.SimLogger()
        slog.log(
            sim.LOG_IO_REQUEST,
            self.my_addr,
            who,
            contentID=device.get_id(),
            other="read",
        )
        ioc = IOClient(tp, who, idf)
        out, status = await ioc.ReadDevice(device, l)
        status = convert_to_io_status(status)
        return out, status

    async def read_available_handler(self, device: Device):
        # search for device.
        # send request to device.
        who = await self.dht_get(device.get_id(), DHTSelect.DEVICE_ID)
        if who is None:
            return False, IO_NONEXIST
        tp = await self.get_peer_transport(who)
        if tp is None:
            return False, IO_NONEXIST

        idf = device.get_local_device_identifier()
        if idf is None:
            return b"", IO_BUSY
        slog = sim.SimLogger()
        slog.log(
            sim.LOG_IO_REQUEST,
            self.my_addr,
            who,
            contentID=device.get_id(),
            other="readavail",
        )
        ioc = IOClient(tp, who, idf)
        out, status = await ioc.ReadAvailable(device)
        logger.debug(f"IO - ReadAvail Output: {out}")
        return out, convert_to_io_status(status)

    async def open_handler(self, device: Device, processID: bytes):
        # search for device.
        # send request to device.
        logger.info("IO - Open request")
        who = await self.dht_get(device.get_id(), DHTSelect.DEVICE_ID)
        if who is None:
            return b"", IO_NONEXIST
        tp = await self.get_peer_transport(who)
        if tp is None:
            return b"", IO_NONEXIST
        slog = sim.SimLogger()
        slog.log(
            sim.LOG_IO_REQUEST,
            self.my_addr,
            who,
            contentID=device.get_id(),
            other="open",
        )
        ioc = IOClient(tp, who, processID)
        out_id, status = await ioc.OpenDevice(device)
        logger.info("IO - Open request done")
        return out_id, convert_to_io_status(status)

    async def close_handler(self, device: Device):
        # search for device.
        # send request to device.
        who = await self.dht_get(device.get_id(), DHTSelect.DEVICE_ID)
        if who is None:
            return IO_NONEXIST
        tp = await self.get_peer_transport(who)
        if tp is None:
            return IO_NONEXIST
        idf = device.get_local_device_identifier()
        if idf is None:
            return IO_BUSY
        slog = sim.SimLogger()
        slog.log(
            sim.LOG_IO_REQUEST,
            self.my_addr,
            who,
            contentID=device.get_id(),
            other="close",
        )
        ioc = IOClient(tp, who, idf)
        status = await ioc.CloseDevice(device)
        return convert_to_io_status(status)

    async def unmount_handler(self, device: Device):
        # search for device.
        # send request to device.
        who = await self.dht_get(device.get_id(), DHTSelect.DEVICE_ID)
        if who is None:
            return IO_NONEXIST
        tp = await self.get_peer_transport(who)
        if tp is None:
            return IO_NONEXIST
        idf = device.get_local_device_identifier()
        if idf is None:
            return b"", IO_BUSY
        slog = sim.SimLogger()
        slog.log(
            sim.LOG_IO_REQUEST,
            self.my_addr,
            who,
            contentID=device.get_id(),
            other="unmount",
        )
        ioc = IOClient(tp, who, idf)
        status = await ioc.UnmountDevice(device)
        return convert_to_io_status(status)

    async def dht_get(
        self, key: bytes, select: DHTSelect, ignore=[]
    ) -> Optional[bytes]:
        """Get a record from the DHT

        Args:
            key (bytes): Key
            select (DHTSelect): DHT to query

        Returns:
            Optional[bytes]: value or None for not found
        """
        # It tries my local loopback.... interface is on local loopback.
        slog = sim.SimLogger()
        session = slog.start_session()
        slog.log(
            sim.LOG_DHT_LOOKUP_START,
            self.my_addr,
            self.my_addr,
            session=session,
            contentID=key,
            select=select,
        )

        value, status, select_in = await self.dht_interface.FetchItem(
            key, select, nodes_visited=ignore, simlog_session=session
        )  # send out.
        if (
            status != DHTStatus.FOUND and status != DHTStatus.OWNED
        ) or status == DHTStatus.ERR:
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
        elif select == DHTSelect.FILE_ID:
            response = self.file_table.get(key)
        elif select == DHTSelect.DEVICE_ID:
            response = self.device_table.get(key)
        else:
            logger.error(f"DHT - Unknown table selected!")
            return  # type: ignore
        return response.data, response.response_code, response.neighbor_addrs

    async def dht_set(
        self,
        key: bytes,
        value: bytes,
        select: DHTSelect,
        nodes_visited: list[bytes] = [],
        fixed_owner=False,
    ) -> tuple[DHTStatus, bytes]:
        """Set value to DHT

        Args:
            key (bytes): key
            value (bytes): value
            select (DHTSelect): DHT to store on

        Returns:
            DHTStatus: Status of operation
        """
        slog = sim.SimLogger()
        session = slog.start_session()
        slog.log(
            sim.LOG_DHT_LOOKUP_START,
            self.my_addr,
            self.my_addr,
            session=session,
            contentID=key,
            select=select,
        )
        status, who = await self.dht_interface.StoreItem(
            key,
            value,
            select,
            nodes_visited=nodes_visited,
            fixed_owner=fixed_owner,
            simlog_session=session,
        )
        return status, who

    async def dht_cache_store(
        self, key: bytes, value: bytes, select: DHTSelect, monitor: bytes
    ):
        """Messaging Services: Store item in DHT cache

        Args:
            key (bytes): Key to store
            value (bytes): Value to store in cache
            select (DHTSelect): DHT to store under
        """
        if select == DHTSelect.PEER_ID:
            self.peer_table.update_addresses(key)
            result = self.peer_table.set_cache(key, value)
            self.task_table.update_addresses(key)
            self.file_table.update_addresses(key)
            self.device_table.update_addresses(key)
            slog = sim.SimLogger()
            slog.log(sim.LOG_DHT_ADDRESS_UPDATE, self.my_addr, key)
            if not (result):
                # I already owned it.
                return

            await self.dht_set_cache_notices(key, value, select, monitor)

        elif select == DHTSelect.TASK_ID:
            r = self.task_table.set_cache(key, value)
            if not (r):
                return  # I already owned it.
            await self.dht_set_cache_notices(key, value, select, monitor)

        elif select == DHTSelect.FILE_ID:
            r = self.file_table.set_cache(key, value)
            if not (r):
                return  # I already owned it.
            await self.dht_set_cache_notices(key, value, select, monitor)

        elif select == DHTSelect.DEVICE_ID:
            r = self.device_table.set_cache(key, value)
            if not (r):
                return  # I already owned it.
            await self.dht_set_cache_notices(key, value, select, monitor)

        else:
            logger.error(f"DHT - Unknown table selected!")

    async def dht_set_cache_notices(
        self, key: bytes, value: bytes, select: DHTSelect, last_chain: bytes
    ):
        logger.debug(
            f"DHT - DHT SET CACHE NOTICES [{key.hex()}] <--- {last_chain.hex()}"
        )
        if key in self.cache_subscriptions[select]:
            logger.debug(f"DHT - DROP DHT SET CACHE NOTICES")
            return  # I already am registered to it.

        if key in self.cache_subscriptions_serve[select]:
            logger.debug(f"DHT - DROP DHT SET CACHE NOTICES 2")
            return  # I am already serving this to others.

        if select == DHTSelect.PEER_ID:
            # cache.
            addr = await self.get_peer_transport(last_chain)
            assert addr is not None
            channel = addr.get_channel()
            self.keep_alive_manager.register_channel_service(
                channel,
                addr.get_string_channel(),
                key,
                lambda: self.peer_cache_maintain_offline(last_chain, key),
                TRIGGER_OFFLINE,
            )

            # Send to chain.
            logger.debug(
                f"DHT - Set plain cache. Register notices dest: {last_chain.hex()}"
            )
            client = DHTClient(addr, last_chain, self.my_addr, self.keep_alive_manager)
            await client.register_notices(key, select)
            self.cache_subscriptions[select].add(key)  # I am subscribed to updates
            self.cache_subscriptions_serve[select][
                key
            ] = set()  # People who connect to me.

        if select == DHTSelect.TASK_ID:
            # cache.
            addr = await self.get_peer_transport(last_chain)
            assert addr is not None
            channel = addr.get_channel()
            self.keep_alive_manager.register_channel_service(
                channel,
                addr.get_string_channel(),
                last_chain,
                lambda: self.task_cache_maintain_offline(last_chain, key, value),
                TRIGGER_OFFLINE,
            )

            # Send to chain.
            logger.debug(
                f"DHT - Set plain cache. Register notices dest: {last_chain.hex()}"
            )
            client = DHTClient(addr, last_chain, self.my_addr, self.keep_alive_manager)
            await client.register_notices(key, select)
            self.cache_subscriptions[select].add(key)  # I am subscribed to updates
            self.cache_subscriptions_serve[select][
                key
            ] = set()  # People who connect to me.

        if select == DHTSelect.FILE_ID:
            # cache.
            addr = await self.get_peer_transport(last_chain)
            assert addr is not None
            channel = addr.get_channel()
            self.keep_alive_manager.register_channel_service(
                channel,
                addr.get_string_channel(),
                last_chain,
                lambda: self.remove_peer_from_address_tables(last_chain),
                TRIGGER_OFFLINE,
            )

            # Send to chain.
            logger.debug(
                f"DHT - Set plain cache. Register notices dest: {last_chain.hex()}"
            )
            client = DHTClient(addr, last_chain, self.my_addr, self.keep_alive_manager)
            await client.register_notices(key, select)
            self.cache_subscriptions[select].add(key)  # I am subscribed to updates
            self.cache_subscriptions_serve[select][
                key
            ] = set()  # People who connect to me.

        if select == DHTSelect.DEVICE_ID:
            # cache.
            addr = await self.get_peer_transport(last_chain)
            assert addr is not None
            channel = addr.get_channel()
            self.keep_alive_manager.register_channel_service(
                channel,
                addr.get_string_channel(),
                key,
                lambda: self.device_maintain_valid_offline(last_chain, key),
                TRIGGER_OFFLINE,
            )

            # Send to chain.
            logger.debug(
                f"DHT - Set plain cache. Register notices dest: {last_chain.hex()}"
            )
            client = DHTClient(addr, last_chain, self.my_addr, self.keep_alive_manager)
            await client.register_notices(key, select)
            self.cache_subscriptions[select].add(key)  # I am subscribed to updates
            self.cache_subscriptions_serve[select][
                key
            ] = set()  # People who connect to me.

        logger.debug(f"DHT - DHT SET CACHE NOTICES DONE")
        logger.info(f"DHT - Listening:")
        self.print_cache_subscriptions_listening()
        logger.info(f"DHT - Serving:")
        self.print_cache_subscriptions_serve()
        logger.info(f"DHT - Peer Table:")
        self.peer_table.fancy_print()
        logger.info(f"DHT - Task Table:")
        self.task_table.fancy_print()

    async def task_cache_maintain_offline(
        self, monitor: bytes, key: bytes, value: bytes
    ):
        self.remove_peer_from_address_tables(monitor)

        # Don't have cache send out another task. Rely on monitor.
        # tv = TaskValue.FromString(value)
        # proc = StarProcess.from_bytes(tv.process_data)
        # task = StarTask.from_bytes(tv.task_data)
        # await self.send_out_single_task(proc, task)

        # owner is offline.... dispatch the task.

    async def dht_set_plain(
        self,
        key: bytes,
        value: bytes,
        select: DHTSelect,
        addr_init: bytes,
        ignore: set[bytes] = set(),
        fixed_owner=False,
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
        logger.debug(f"DHT - DHT SET PLAIN")
        if select == DHTSelect.PEER_ID:
            self.peer_table.update_addresses(key)
            self.task_table.update_addresses(key)
            self.file_table.update_addresses(key)
            self.device_table.update_addresses(key)
            slog = sim.SimLogger()
            slog.log(sim.LOG_DHT_ADDRESS_UPDATE, self.my_addr, key)
            r = self.peer_table.set(key, value, ignore=ignore)
            if r.response_code == DHTStatus.OWNED:
                #  Add callback to KeepAlive
                addr = StarAddress.from_bytes(value)
                addr.set_keep_alive(self.keep_alive_manager)
                channel = addr.get_channel()
                logger.debug(f"DHT - Set plain")
                if addr.get_string_channel() == self.local_addr.get_string_channel():
                    logger.debug(f"DHT - Skip - host on my own")
                    if key not in self.cache_subscriptions_serve[select]:
                        self.cache_subscriptions_serve[select][key] = set()
                    logger.debug(f"DHT - END DHT SET PLAIN")
                    return r.data, r.response_code, r.neighbor_addrs
                    # QUIT. Don't track myself.

                logger.debug(
                    f"DHT - Create callback to maintain peer connection online"
                )
                self.keep_alive_manager.register_channel_service(
                    channel,
                    addr.get_string_channel(),
                    key,
                    lambda: self.peer_maintain_valid_offline(key),
                    TRIGGER_OFFLINE,
                )
                if key not in self.cache_subscriptions_serve[select]:
                    self.cache_subscriptions_serve[select][key] = set()

        elif select == DHTSelect.TASK_ID:
            # Do not post to cache for Task Alloc.
            # Put your address in the owner field!
            tsk = TaskValue.FromString(value)
            tsk.address = self.my_addr
            r = self.task_table.set(
                key, tsk.SerializeToString(), post_to_cache=False, ignore=ignore
            )
            if r.response_code == DHTStatus.OWNED:
                # DO NOTHING.... I can serve cache subs to others though.
                if key not in self.cache_subscriptions_serve[select]:
                    self.cache_subscriptions_serve[select][key] = set()
                await self.send_task_to_engine(value)

        elif select == DHTSelect.FILE_ID:
            r = self.file_table.set(
                key, self.my_addr, post_to_cache=False, ignore=ignore
            )
            if r.response_code == DHTStatus.OWNED:
                logger.info(f"FILE - File stored! {key.hex()}")

                # I can serve cache subs to others though.
                if key not in self.cache_subscriptions_serve[select]:
                    self.cache_subscriptions_serve[select][key] = set()

                hf = HostedFile.from_key(key)
                hf.local_filepath = self.file_manager.file_save_dir
                monitor_peer = await self.create_file_monitor_request(hf, self.my_addr)
                self.file_manager.host_file(hf, monitor_peer, is_monitor=False)

        elif select == DHTSelect.DEVICE_ID:
            r = self.device_table.set(
                key, value, post_to_cache=True, ignore=ignore, neighbors=2
            )
            if r.response_code == DHTStatus.OWNED and fixed_owner:
                #  Add callback to KeepAlive
                # value is the peer it is stored on!
                # tp = self.get_peer_transport(value)
                # assert tp is not None
                if value != self.my_addr:
                    raise ValueError("Only own on self for devices!")
                    # channel = tp.get_channel()
                    # logger.debug(
                    #     f"IO - Create callback to maintain device connection online"
                    # )
                    # self.keep_alive_manager.register_channel_service(
                    #     channel,
                    #     tp.get_string_channel(),
                    #     key,
                    #     lambda: self.device_maintain_valid_offline(key, value),
                    #     TRIGGER_OFFLINE,
                    # )
                r.response_code = DHTStatus.FOUND
                if key not in self.cache_subscriptions_serve[select]:
                    self.cache_subscriptions_serve[select][key] = set()

            elif r.response_code == DHTStatus.OWNED:
                self.device_table.remove(key)
                await self.dht_cache_store(
                    key, value, DHTSelect.DEVICE_ID, value
                )  # value owns it.

                if key not in self.cache_subscriptions_serve[select]:
                    self.cache_subscriptions_serve[select][key] = set()

                tp = await self.get_peer_transport(value)
                assert tp is not None
                self.keep_alive_manager.register_channel_service(
                    tp.get_channel(),
                    tp.get_string_channel(),
                    key,
                    lambda: self.device_maintain_valid_offline(key, value),
                    TRIGGER_OFFLINE,
                )

            logger.warning(f"IO - Device table")
            self.device_table.fancy_print()
            logger.warning(f"IO - Subscriptions")
            self.print_cache_subscriptions_listening()

        else:
            logger.error(f"DHT - Unknown table selected!")
            return  # type: ignore

        logger.debug(f"DHT - END DHT SET PLAIN")
        return r.data, r.response_code, r.neighbor_addrs

    async def general_offline_cb(self, peer):
        # see if peer is currently being served.
        if self.peer_table.exists(peer):
            # I do have it.
            await self.dht_delete_plain(peer, DHTSelect.PEER_ID)

    async def dht_update(self, key: bytes, select: DHTSelect):
        # for updating records on the DHT that you might not own.
        pass

    async def dht_delete_plain(self, key: bytes, select: DHTSelect):
        if select == DHTSelect.PEER_ID:
            if not (self.peer_table.exists(key)):
                return DHTStatus.ERR

            log = sim.SimLogger()
            log.log(sim.LOG_DHT_NODE_DELETE, key, select=select)

            self.remove_peer_from_address_tables(key)
            await self.dht_delete_notice_plain(key, select)
            self.peer_table.remove(key)

        if select == DHTSelect.DEVICE_ID:
            if not (self.device_table.exists(key)):
                return DHTStatus.ERR

            await self.dht_delete_notice_plain(key, select)
            self.device_table.remove(key)

        return DHTStatus.OK

    async def dht_update_plain(self, key: bytes, select: DHTSelect):
        pass

    async def dht_delete_notice_plain(self, key: bytes, select: DHTSelect):
        logger.debug(f"DHT - DHT DELETE NOTICE PLAIN")
        if select == DHTSelect.PEER_ID:
            if not (self.peer_table.exists(key)):
                logger.debug(f"DHT - DHT DELETE NOTICE PLAIN ERR")
                return DHTStatus.ERR
            self.peer_table.remove(key)
            self.remove_peer_from_address_tables(key)
            await self.send_deletion_notice(key, select)
            if key in self.cache_subscriptions[select]:
                self.cache_subscriptions[select].remove(key)
            if key in self.cache_subscriptions_serve[select]:
                del self.cache_subscriptions_serve[select][key]

            logger.warning(f"DHT - Final Node2 - delete")
            self.peer_table.fancy_print()

            logger.warning(f"DHT - Final Keep Alive listening  - delete")
            self.print_keep_alives()

            logger.warning(f"DHT - Final subscriptions listening  - delete")
            self.print_cache_subscriptions_listening()

        if select == DHTSelect.DEVICE_ID:
            if not (self.device_table.exists(key)):
                logger.debug(f"DHT - DHT DELETE NOTICE PLAIN ERR")
                return DHTStatus.ERR
            self.device_table.remove(key)

            await self.send_deletion_notice(key, select)
            if key in self.cache_subscriptions[select]:
                self.cache_subscriptions[select].remove(key)
            if key in self.cache_subscriptions_serve[select]:
                del self.cache_subscriptions_serve[select][key]

            logger.warning(f"DHT - Final Device ID - delete")
            self.device_table.fancy_print()

            logger.warning(f"DHT - Final  Device ID listening  - delete")
            self.print_keep_alives()

            logger.warning(f"DHT - Final subscriptions listening  - delete")
            self.print_cache_subscriptions_listening()

        logger.debug(f"DHT - DHT DELETE NOTICE PLAIN OK")
        return DHTStatus.OK

    async def dht_update_notice_plain(self, key: bytes, select: DHTSelect):
        pass


#             RPC              RPC
# task_create --> task_allocate --> dht_store
