# KeepAlive management.
# Register channels to check.


import asyncio
from typing import Callable, Optional
import grpc

from src.communications.KeepAliveService import KeepAliveComm

TRIGGER_OFFLINE = 1
TRIGGER_TIMEOUT = 2


class KeepAlive_Channel:
    def __init__(self, channel: grpc.aio.Channel):
        self.comm = KeepAliveComm(channel)
        self.connected = False
        self.callbacks: dict[int, list[Callable]] = {}

    def add_callbacks(self, trigger: int, callback: Callable):
        if trigger not in self.callbacks:
            self.callbacks[trigger] = [callback]
            return
        self.callbacks[trigger].append(callback)

    def is_connected(self) -> bool:
        return self.connected

    async def verify(self) -> bool:
        try:
            self.connected = await self.comm.SendPing()
        except:
            self.connected = False
        return self.connected

    async def heartbeat(self, custom_data):
        self.comm.SendHeartbeat(custom_data)


class KeepAlive_Management:
    def __init__(self):
        asyncio.create_task(self.keep_alive_task())
        self.channels: dict[grpc.aio.Channel, KeepAlive_Channel] = {}
        self.custom_data: dict[grpc.aio.Channel, dict[str, Callable]] = {}
        self.roundrobin_channels: list[grpc.aio.Channel] = []
        self.channel_map: dict[str, grpc.aio.Channel] = {}

    def get_channel(self, string: str) -> grpc.aio.Channel:
        if string not in self.channel_map:
            self.channel_map[string] = grpc.aio.insecure_channel(string)
        return self.channel_map[string]

    def register_channel_service(
        self,
        channel: grpc.aio.Channel,
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

        if trigger == TRIGGER_TIMEOUT:
            trigger = timeout_sec * 0.1 + 2  # type: ignore

        self.channels[channel].add_callbacks(trigger, async_callback)

        if custom_data_label in self.custom_data[channel]:
            self.custom_data[channel][custom_data_label] = custom_data_callback
        else:
            self.custom_data[channel][custom_data_label] = custom_data_callback

        return self.channels[channel]

    async def keep_alive_task(self):
        counter = 0
        while True:
            if len(self.channels) == 0:
                await asyncio.sleep(
                    1
                )  # even keep alives for everyone... later can do something different.
                continue
            await asyncio.sleep(1 / len(self.channels))

            channel = self.roundrobin_channels[counter]
            counter += 1
            if counter > len(self.channels):
                counter = 0

            # get custom data callbacks.
            out = {}
            for lbl, cb in self.custom_data[channel].items():
                if lbl is None or cb is None:
                    continue
                out[lbl] = await cb()

            asyncio.create_task(channel.heartbeat(out))  # heartbeat


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
