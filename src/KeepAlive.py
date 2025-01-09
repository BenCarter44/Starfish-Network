# KeepAlive management.
# Register channels to check.


import asyncio
import time
from typing import Callable, Optional
import grpc

import logging

logger = logging.getLogger(__name__)


from src.communications.KeepAliveService import KeepAliveComm

TRIGGER_OFFLINE = 1
TRIGGER_TIMEOUT = 2

OFFLINE_TIMEOUT = 10
HEARTBEAT_INTERVAL = 2


class KeepAlive_Channel:
    def __init__(self, channel: grpc.aio.Channel):
        self.comm = KeepAliveComm(channel)
        self.connected = False
        self.callbacks: dict[int, list[Callable]] = {}
        self.last_seen = 0.0
        self.peer_id_assoc: Optional[bytes] = None

    def mark_peer_id(self, peer: bytes):
        self.peer_id_assoc = peer

    def add_callbacks(self, trigger: int, callback: Callable):
        if trigger not in self.callbacks:
            self.callbacks[trigger] = [callback]
            return
        self.callbacks[trigger].append(callback)

    def is_connected(self) -> bool:
        return self.connected

    async def callback_loop(self):
        while True:
            await asyncio.sleep(0.1)
            if time.time() - self.last_seen > OFFLINE_TIMEOUT:
                # offline!
                asyncio.create_task(self.mark_offline())

    async def verify(self) -> bool:
        try:
            self.connected = await self.comm.SendPing()
            if self.connected:
                self.last_seen = time.time()
        except:
            self.connected = False
        return self.connected

    async def heartbeat(self, custom_data):
        try:
            hb = await self.comm.SendHeartbeat(custom_data)
        # custom data back.
        except:
            # offline! ...
            return
        self.update()

    def update(self):
        self.last_seen = time.time()
        self.connected = True

    async def mark_offline(self):
        self.connected = False
        for cb in self.callbacks[TRIGGER_OFFLINE]:
            await cb(self.peer_id_assoc)

    def is_due_for_heartbeat(self):
        return time.time() - self.last_seen > HEARTBEAT_INTERVAL


class KeepAlive_Management:
    def __init__(self, my_addr: bytes):
        asyncio.create_task(self.keep_alive_task())
        self.channels: dict[grpc.aio.Channel, KeepAlive_Channel] = {}
        self.custom_data: dict[grpc.aio.Channel, dict[str, Callable]] = {}
        self.roundrobin_channels: list[grpc.aio.Channel] = []
        self.channel_map: dict[str, grpc.aio.Channel] = {}

    def get_channel(self, string: str) -> grpc.aio.Channel:
        if string not in self.channel_map:
            self.channel_map[string] = grpc.aio.insecure_channel(string)
        return self.channel_map[string]

    def get_kp_channel(self, addr) -> KeepAlive_Channel:
        s = addr.get_string_channel()
        channel = self.get_channel(s)
        if channel not in self.channels:
            self.channels[channel] = KeepAlive_Channel(channel)
            self.custom_data[channel] = {}
            self.roundrobin_channels.append(channel)
        return self.channels[channel]

    async def receive_ping(self, servicer_client):
        # get channel. If I have the channel, update its keep alive
        channel_recv_peer = servicer_client.replace("ipv4:", "tcp://")
        if channel_recv_peer not in self.channel_map:
            return  # I didn't open a channel to it, skip

        channel = self.channel_map[channel_recv_peer]
        if channel not in self.channels:
            return  # I don't have any callbacks registered to it.

        self.channels[channel].update()
        return

    async def receive_heartbeat_service(self, servicer_client: str, custom_data_in):
        # get channel. If I have the channel, update its keep alive
        channel_recv_peer = servicer_client.replace("ipv4:", "tcp://")
        if channel_recv_peer not in self.channel_map:
            return custom_data_in  # I didn't open a channel to it, skip

        channel = self.channel_map[channel_recv_peer]
        if channel not in self.channels:
            return custom_data_in  # I don't have any callbacks registered to it.

        self.channels[channel].update()
        # do something on heartbeat?
        return custom_data_in

    def register_channel_service(
        self,
        channel: grpc.aio.Channel,
        channel_string: str,
        async_callback: Callable,
        trigger: int,
        custom_data_callback: Optional[Callable] = None,
        custom_data_label: Optional[str] = None,
        timeout_sec: float = 0,
    ) -> KeepAlive_Channel:

        if channel not in self.channels:
            self.channels[channel] = KeepAlive_Channel(channel)
            self.custom_data[channel] = {}
            self.roundrobin_channels.append(channel)
            s = channel_string  # type: ignore
            self.channel_map[s] = channel

        if trigger == TRIGGER_TIMEOUT:
            trigger = timeout_sec * 0.1 + 2  # type: ignore

        self.channels[channel].add_callbacks(trigger, async_callback)

        if custom_data_label is None or custom_data_callback is None:
            return self.channels[channel]

        if custom_data_label in self.custom_data[channel]:
            self.custom_data[channel][custom_data_label] = custom_data_callback
        else:
            self.custom_data[channel][custom_data_label] = custom_data_callback

        return self.channels[channel]

    async def keep_alive_task(self):
        logger.debug("Keep Alive task running")
        counter = 0
        while True:
            if len(self.channels) == 0:
                await asyncio.sleep(
                    1
                )  # even keepalive delay for everyone... later can do something different.
                continue

            channel = self.roundrobin_channels[counter]
            counter += 1
            if counter > len(self.channels):
                counter = 0

            if not (self.channels[channel].is_due_for_heartbeat()):
                continue

            # get custom data callbacks.
            out = {}
            for lbl, cb in self.custom_data[channel].items():
                if lbl is None or cb is None:
                    continue
                out[lbl] = await cb()

            asyncio.create_task(
                self.channels[channel].heartbeat(out)
            )  # heartbeat request.
            await asyncio.sleep(HEARTBEAT_INTERVAL / len(self.channels))


"""
# Peer discovery:

Bootstrap:
When posting your own address, track the addresses that own the peerID.  --> TRACK OWNER (register_channel_service)
Do a PING to the addresses / accept PONG --> VERIFY ALIVE. (verify, not callback.)
DHT OWN: track the peer with keep alive. When offline, delete record (non-standard). Inform cache peers --> INIT OFFLINE
DHT initiator: track store peers. When offline, send out address again. (standard) --> OWNER OFFLINE


Cache:
Open connection to OWNER / recent chain. When offline, run PING, if success, send out address. If no ping, drop. Inform cache peers.

Callbacks:
1. when_peer_offline()
2. upstream_chain_update()   --> owner sends update to cache.

-----------------------------

# Task Management.

Allocation req receiver: Do nothing
Allocation req sender: track store peers. When offline, send out value again. (standard)

Cache:
Open connection to OWNER / recent chain. When offline, send out value again (add old peer to chain)

Event sender (this means that I also am an engine for a different task!!)
If timeout: Send out the requested task to network with ignore chain of old PEER.

CHANGE: Cache also stores callable. This allows cache to spawn tasks!
"""
