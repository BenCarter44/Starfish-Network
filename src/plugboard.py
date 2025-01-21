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

        self.keep_alive_manager = KeepAlive_Management(node_id, self.general_offline_cb)
        self.local_addr = local_addr
        self.local_addr.set_keep_alive(self.keep_alive_manager)

        self.peer_table = DHT(self.my_addr)
        self.peer_table.update_addresses(node_id)
        self.peer_table.set(node_id, local_addr.to_bytes())
        self.cache_subscriptions_serve: dict[DHTSelect, dict[bytes, set[bytes]]] = {
            DHTSelect.PEER_ID: {self.my_addr: set()},
            DHTSelect.TASK_ID: {self.my_addr: set()},
        }  # stores KEY and peers caching.

        self.cache_subscriptions: dict[DHTSelect, set[bytes]] = {
            DHTSelect.PEER_ID: set(),
            DHTSelect.TASK_ID: set(),
        }

        self.task_table = DHT(self.my_addr)
        self.task_table.update_addresses(node_id)

        logger.info(f"Creating local channel: {self.local_addr.get_string_channel()}")
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

        # Process ID --> Peer ID
        self.monitor_servers: dict[bytes, bytes] = {}

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
                        f"PEER_TABLE \t [{key.hex()}] --forward--> {host.hex()}"
                    )

    def print_cache_subscriptions_listening(self):
        for select in self.cache_subscriptions:
            if select != DHTSelect.PEER_ID:
                continue
            for key in self.cache_subscriptions[select]:
                logger.info(f"PEER_TABLE \t [{key.hex()}]")

    def remove_peer_from_address_tables(self, peer):
        self.peer_table.remove_address(peer)
        self.task_table.remove_address(peer)

    async def get_peer_transport(self, addr: bytes, ignore=[]) -> Optional[StarAddress]:
        """Use the DHT to get transport address given Node ID

        Args:
            addr (bytes): Node ID to query

        Returns:
            Optional[StarAddress]: StarAddress of peer or None if not found.
        """
        logger.debug("GET PEER TRANSPORT")
        # Peer ID. Get StarAddress
        tp_b = await self.dht_get(addr, DHTSelect.PEER_ID, ignore=ignore)
        if tp_b is None:
            logger.debug("DONE PEER TRANSPORT NONE")
            return None
        # logger.debug(f"TP: {tp_b.hex()} - {tp_b}")
        tp = StarAddress.from_bytes(tp_b)
        tp.set_keep_alive(self.keep_alive_manager)
        logger.debug("DONE PEER TRANSPORT")
        return tp

    async def add_peer(self, addr: bytes, tp: StarAddress):
        """Add a peer node to the DHT

        Args:
            addr (bytes): Node ID
            tp (StarAddress): Transport Address
        """
        logger.debug(f"Add peer {addr.hex()} at {tp.get_string_channel()}")
        owners, who = await self.dht_set(addr, tp.to_bytes(), DHTSelect.PEER_ID)
        logger.debug(f"Add peer done")
        if addr != self.my_addr:
            return
        # Track owners.
        # who! currently just one owner. TODO.
        logger.debug(f"Creating listener to storer of my address - {who.hex()}")
        tp = await self.get_peer_transport(who)  # type: ignore
        assert tp is not None
        tp.set_keep_alive(self.keep_alive_manager)
        channel = tp.get_channel()
        if tp.get_string_channel() == self.local_addr.get_string_channel():
            logger.debug("Not creating listener to storer of my address as it's me!")
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
            logger.error("Self CB peer ID None!")
            return

        logger.info(
            f"Owner of my transport address {self.my_addr.hex()} went offline. Resending"
        )

        # store-er went offline! Resend address.
        self.remove_peer_from_address_tables(peer_id)
        await self.add_peer(self.my_addr, self.local_addr)

    async def peer_maintain_valid_offline(self, peer_id: Optional[bytes]):
        # peer_id went offline. I own the peer's address. Delete
        if peer_id is None:
            logger.error("Maintain CB can't be None!")
            return

        await self.dht_delete_plain(peer_id, DHTSelect.PEER_ID)

    async def send_deletion_notice(self, key, select):
        tmp = set()

        logger.warning("Final subscriptions serving  - delete")
        self.print_cache_subscriptions_serve()
        logger.debug(self.cache_subscriptions_serve)
        logger.debug(self.cache_subscriptions_serve[select][key])
        logger.debug(select)
        logger.debug(key)

        for cacher in self.cache_subscriptions_serve[select][key]:
            logger.debug(cacher.hex())

            tp = await self.get_peer_transport(cacher)
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
        logger.debug("PERFORM BOOTSTRAP")
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
        logger.debug("Sending out my address...")
        await self.add_peer(self.my_addr, self.local_addr)
        logger.debug("PERFORM BOOTSTRAP DONE")

    async def dispatch_event(self, evt: Event, proc: StarProcess):
        """Dispatch an event to either the local engine or to the network

        Args:
            evt (Event): Event to dispatch
        """
        logger.info(f"Dispatch event to task: {evt.target.get_id().hex()}")
        logger.debug(evt)
        assert str(evt).find("Event object") != -1
        # Sends to local.
        resp = await self.task_interface.SendEvent(evt)

        if resp.status == DHTStatus.NOT_FOUND:
            logger.error("Unable to deliver event to node!")

        logger.info(f"Dispatch event DONE!")
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
            logger.error(f"Owner for task {task.get_id().hex()} not found!")
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
        logger.warning(f"Stored Task! {task.get_id().hex()}")
        self.task_table.fancy_print()
        proc = StarProcess.from_bytes(obj.process_data)
        assert task.get_callable() != b""

        # Require a Monitor!
        await self.cb_monitor_offline(proc, task)

        self.engine.import_task(task, proc)

    async def cb_monitor_offline(
        self, proc: StarProcess, task: StarTask, monitor_peer_old: bytes = b""
    ):
        assert task.get_callable() != b""
        # On monitor fail, pick a new monitor

        # Pick a random node (later adjust to be one that is close.)
        # Don't pick where it came from or myself
        monitor_peer = self.peer_table.get_random_key(
            set([self.my_addr, monitor_peer_old])
        )
        if monitor_peer is None:
            logger.warning(
                "There are no other peers send to monitor! You need more peers! Operating solo!"
            )
            return

        assert monitor_peer is not None

        tp: StarAddress | None = await self.get_peer_transport(monitor_peer)
        assert tp is not None

        task_peer = TaskPeer(tp, monitor_peer)

        await task_peer.SendMonitor_Request(proc, self.my_addr, task)  # have monitor!

        self.monitor_servers[proc.get_id()] = monitor_peer

        async def tmp():
            self.remove_peer_from_address_tables(monitor_peer)
            await self.cb_monitor_offline(proc, task, monitor_peer)

        kp_channel = self.keep_alive_manager.register_channel_service(
            tp.get_channel(),
            tp.get_string_channel(),
            monitor_peer,
            tmp,
            TRIGGER_OFFLINE,
        )
        kp_channel.update()

    async def allocate_program(self, proc: StarProcess):
        """Node API: Allocate a task to the engine or to network

        Args:
            task (StarTask): Program to allocate
        """

        for task in proc.get_tasks():
            assert task.get_callable() != b""
            who = await self.send_out_single_task(proc, task)
            logger.info(f"WHO: {who.hex()}")
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
        _, who = await self.dht_set(
            task.get_id(),
            tv.SerializeToString(),
            DHTSelect.TASK_ID,
            nodes_visited=ignore,
        )

        # Track owners.
        # who! currently just one owner. TODO.
        logger.debug(f"Creating listener to storer of my task - {who.hex()}")
        logger.debug(f"Who: {who.hex()}")
        tp = await self.get_peer_transport(who, ignore=ignore)  # type: ignore
        assert tp is not None
        tp.set_keep_alive(self.keep_alive_manager)
        channel = tp.get_channel()
        if tp.get_string_channel() == self.local_addr.get_string_channel():
            logger.debug("Not creating listener to storer of my address as it's me!")
            return self.my_addr
        self.keep_alive_manager.register_channel_service(
            channel,
            tp.get_string_channel(),
            who,
            lambda: self.task_self_cb_offline(process, task, who),
            TRIGGER_OFFLINE,
        )
        return who

    async def task_self_cb_offline(
        self, process: StarProcess, task: StarTask, who: bytes
    ):
        # Owner for task went offline. Respawn
        logger.warning(f"Storer went offline for task: {task.get_id().hex()}")

        # Don't send anything anywhere. Have monitor do that.
        # who2 = await self.send_out_single_task(process, task, ignore=[who])
        # # require at least two different owners at all times!
        # await self.send_out_single_task(process, task, ignore=[who, who2])

    async def receive_monitor_request(
        self, proc: StarProcess, who: bytes, task: StarTask
    ):
        self.monitor_service.add_process(proc, who)
        # Add keepalive

        tp = await self.get_peer_transport(who)
        assert tp is not None
        assert task.get_callable() != b""
        self.keep_alive_manager.register_channel_service(
            tp.get_channel(),
            tp.get_string_channel(),
            who,
            lambda: self.cb_owner_offline(
                proc,
                task,
                who,
            ),
            TRIGGER_OFFLINE,
        )

    async def cb_owner_offline(self, proc: StarProcess, task: StarTask, who: bytes):
        logger.warning("CB OWNER OFFLINE")
        # Owner is offline!
        await self.send_out_single_task(proc, task, ignore=[who, self.my_addr])
        evt = self.monitor_service.recall_most_recent_event(
            who, task.get_process_id(), task.get_id()
        )
        if evt is None:
            logger.debug("No event found. Skip")
            return
        logger.warning("CB OWNER OFFLINE Dispatch Resume Event!")
        await self.dispatch_event(evt, proc)  # resume execution.
        # Send out the task to someone else!

    async def receive_checkpoint(
        self, proc: bytes, who: bytes, event_origin: Event | None, event_to: Event
    ):
        # called from server SendCheckpoint()

        self.monitor_service.add_checkpoint(who, event_origin, event_to)

    async def send_checkpoint(
        self,
        proc_id: bytes,
        event_origin: Event | None,
        event_target: Event,
    ):
        # Called from send_event()
        # Alert my monitor

        logger.debug(self.monitor_servers)
        if proc_id not in self.monitor_servers:
            logger.warning(f"No monitor found for process: {proc_id}")
            return
        monitor_peer = self.monitor_servers[proc_id]
        logger.debug(f"Send checkpoint {monitor_peer.hex()}")
        tp = await self.get_peer_transport(monitor_peer)
        assert tp is not None
        taskClient = TaskPeer(tp, monitor_peer)
        await taskClient.SendCheckpoint(
            proc_id, event_origin, event_target, self.my_addr
        )

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
        value, status, select_in = await self.dht_interface.FetchItem(
            key, select, nodes_visited=ignore
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
        else:
            logger.error("Unknown table selected!")
            return  # type: ignore
        return response.data, response.response_code, response.neighbor_addrs

    async def dht_set(
        self,
        key: bytes,
        value: bytes,
        select: DHTSelect,
        nodes_visited: list[bytes] = [],
    ) -> tuple[DHTStatus, bytes]:
        """Set value to DHT

        Args:
            key (bytes): key
            value (bytes): value
            select (DHTSelect): DHT to store on

        Returns:
            DHTStatus: Status of operation
        """

        status, who = await self.dht_interface.StoreItem(
            key, value, select, nodes_visited=nodes_visited
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
            if not (result):
                # I already owned it.
                return

            await self.dht_set_cache_notices(key, value, select, monitor)

        elif select == DHTSelect.TASK_ID:
            r = self.task_table.set_cache(key, value)
            await self.dht_set_cache_notices(key, value, select, monitor)

        else:
            logger.error("Unknown table selected!")

    async def dht_set_cache_notices(
        self, key: bytes, value: bytes, select: DHTSelect, last_chain: bytes
    ):
        logger.debug(f"DHT SET CACHE NOTICES [{key.hex()}] <--- {last_chain.hex()}")
        if key in self.cache_subscriptions[select]:
            logger.debug("DROP DHT SET CACHE NOTICES")
            return  # I already am registered to it.

        if key in self.cache_subscriptions_serve[select]:
            logger.debug("DROP DHT SET CACHE NOTICES 2")
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
            logger.debug(f"Set plain cache. Register notices dest: {last_chain.hex()}")
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
            logger.debug(f"Set plain cache. Register notices dest: {last_chain.hex()}")
            client = DHTClient(addr, last_chain, self.my_addr, self.keep_alive_manager)
            await client.register_notices(key, select)
            self.cache_subscriptions[select].add(key)  # I am subscribed to updates
            self.cache_subscriptions_serve[select][
                key
            ] = set()  # People who connect to me.

        logger.debug("DHT SET CACHE NOTICES DONE")
        logger.info("Listening:")
        self.print_cache_subscriptions_listening()
        logger.info("Serving:")
        self.print_cache_subscriptions_serve()
        logger.info("Peer Table:")
        self.peer_table.fancy_print()
        logger.info("Task Table:")
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
        logger.debug("DHT SET PLAIN")
        if select == DHTSelect.PEER_ID:
            self.peer_table.update_addresses(key)
            self.task_table.update_addresses(key)
            r = self.peer_table.set(key, value, ignore=ignore)
            if r.response_code == DHTStatus.OWNED:
                #  Add callback to KeepAlive
                addr = StarAddress.from_bytes(value)
                addr.set_keep_alive(self.keep_alive_manager)
                channel = addr.get_channel()
                logger.debug("Set plain")
                if addr.get_string_channel() == self.local_addr.get_string_channel():
                    logger.debug("Skip - host on my own")
                    if key not in self.cache_subscriptions_serve[select]:
                        self.cache_subscriptions_serve[select][key] = set()
                    logger.debug("END DHT SET PLAIN")
                    return r.data, r.response_code, r.neighbor_addrs
                    # QUIT. Don't track myself.

                logger.debug("Create callback to maintain peer connection online")
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
        else:
            logger.error("Unknown table selected!")
            return  # type: ignore

        logger.debug("END DHT SET PLAIN")
        return r.data, r.response_code, r.neighbor_addrs

    async def general_offline_cb(self, peer):
        # see if peer is currently being served.
        if self.peer_table.exists(peer):
            # I do have it.
            await self.dht_delete_plain(peer, DHTSelect.PEER_ID)

    async def dht_delete_plain(self, key: bytes, select: DHTSelect):
        if select == DHTSelect.PEER_ID:
            if not (self.peer_table.exists(key)):
                return DHTStatus.ERR

            self.remove_peer_from_address_tables(key)
            await self.dht_delete_notice_plain(key, select)
            self.peer_table.remove(key)
        return DHTStatus.OK

    async def dht_update_plain(self, key: bytes, select: DHTSelect):
        pass

    async def dht_delete_notice_plain(self, key: bytes, select: DHTSelect):
        logger.debug("DHT DELETE NOTICE PLAIN")
        if select == DHTSelect.PEER_ID:
            if not (self.peer_table.exists(key)):
                logger.debug("DHT DELETE NOTICE PLAIN ERR")
                return DHTStatus.ERR
            self.peer_table.remove(key)
            self.remove_peer_from_address_tables(key)
            await self.send_deletion_notice(key, select)
            if key in self.cache_subscriptions[select]:
                self.cache_subscriptions[select].remove(key)
            if key in self.cache_subscriptions_serve[select]:
                del self.cache_subscriptions_serve[select][key]

            logger.warning("Final Node2 - delete")
            self.peer_table.fancy_print()

            logger.warning("Final Keep Alive listening  - delete")
            self.print_keep_alives()

            logger.warning("Final subscriptions listening  - delete")
            self.print_cache_subscriptions_listening()

        logger.debug("DHT DELETE NOTICE PLAIN OK")
        return DHTStatus.OK

    async def dht_update_notice_plain(self, key: bytes, select: DHTSelect):
        pass


#             RPC              RPC
# task_create --> task_allocate --> dht_store
