# KeepAlive management.
# Register channels to check.


import asyncio
import time
from typing import Callable, Optional
import grpc

import logging

from src.core.star_components import StarAddress

logger = logging.getLogger(__name__)


from src.communications.KeepAliveService import KeepAliveComm

TRIGGER_OFFLINE = 1
TRIGGER_TIMEOUT = 2

OFFLINE_TIMEOUT = 10
HEARTBEAT_INTERVAL = 1
FAIL_MAX = 3
MIN_TEST_WINDOW = 0.2


class KeepAlive_Channel:
    def __init__(self, channel_string: str):
        channel = grpc.aio.insecure_channel(channel_string)
        self.comm = KeepAliveComm(channel)
        self.connected = True
        self.callbacks: dict[int, list[Callable]] = {
            TRIGGER_OFFLINE: [],
            TRIGGER_TIMEOUT: [],
        }
        self.last_seen = 0.0
        self.peer_id_assoc: bytes = b""
        self.channel = channel
        self.kill_count = 0
        self.is_closed = False

    def mark_peer_id(self, peer: bytes):
        self.peer_id_assoc = peer

    def add_callbacks(self, trigger: int, callback: Callable):
        logger.debug(f"KEEPALIVE - Add callback: {callback} - {trigger}")

        self.callbacks[trigger].append(callback)

        # if trigger not in self.callbacks:
        #     self.callbacks[trigger] = [callback]
        #     return
        # self.callbacks[trigger].append(callback)

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

    async def heartbeat(self, i):
        logger.debug(f"KEEPALIVE - Send Heartbeat request: {self.peer_id_assoc.hex()}")
        try:
            hb = await self.comm.SendHeartbeat(self.peer_id_assoc)
        except:
            hb = False
        if not (hb):
            # offline!
            self.kill_count += 1
        else:
            self.update()

        if self.kill_count > FAIL_MAX:
            await self.mark_offline()
            return

    async def kill_update(self):
        self.kill_count += 1
        if self.kill_count > FAIL_MAX:
            await self.mark_offline()
            return

    def update(self):
        # logger.info(f"UPDATE: {self.peer_id_assoc.hex()}")
        self.last_seen = time.time()
        self.connected = True
        if self.kill_count > 0:
            self.kill_count -= 1

    async def mark_offline(self):
        if self.is_closed:
            return
        self.connected = False
        logger.warning(
            f"KEEPALIVE - PEER OFFLINE! {self.peer_id_assoc.hex()} CALL: {self.callbacks[TRIGGER_OFFLINE]}"
        )

        for cb in self.callbacks[TRIGGER_OFFLINE]:
            await cb()

        await self.channel.close()
        self.is_closed = True

    def is_due_for_heartbeat(self):
        return time.time() - self.last_seen > HEARTBEAT_INTERVAL


class KeepAlive_Management:
    def __init__(self, my_addr: bytes, default_offline):
        asyncio.create_task(self.keep_alive_task())
        self.channels: dict[str, KeepAlive_Channel] = {}
        self.roundrobin_channels: list[str] = []
        self.default_offline = default_offline

    def fancy_print(self):
        for s in self.channels:
            logger.info(
                f"KEEPALIVE - {s} : {self.channels[s].is_connected()} - {self.channels[s].last_seen}"
            )

    def get_channel(self, string: str) -> grpc.aio.Channel:
        if string not in self.channels:
            self.channels[string] = KeepAlive_Channel(string)
        return self.channels[string].channel

    def get_kp_channel(self, addr: StarAddress, peer: bytes) -> KeepAlive_Channel:
        string = addr.get_string_channel()
        self.get_channel(string)
        self.channels[string].peer_id_assoc = peer
        return self.channels[string]

    async def test(self, tp: StarAddress, peer: bytes):
        if tp is None:
            return False

        kp = self.get_kp_channel(tp, peer)
        start = kp.kill_count
        if not (kp.is_connected()):
            logger.debug(f"KEEPALIVE - Test query to {peer.hex()} - NOT CON")
            return False
        if kp.last_seen + MIN_TEST_WINDOW > time.time():
            logger.debug(f"KEEPALIVE - Test query to {peer.hex()} - SKIP")
            return True
        logger.debug(f"KEEPALIVE - Test query to {peer.hex()}")
        await kp.heartbeat(False)
        return kp.kill_count == start and kp.is_connected()
        # return kp.is_connected()

    async def receive_ping(self, servicer_client):
        # get channel. If I have the channel, update its keep alive
        channel_recv_peer = servicer_client.replace("ipv4:", "")

        if channel_recv_peer not in self.channels:
            return  # Unknown!

        logger.debug(f"KEEPALIVE - Receive ping from: {channel_recv_peer}")
        self.channels[channel_recv_peer].update()
        return

    async def receive_heartbeat_service(self, out):
        # logger.debug(f"Recv heartbeat request")
        # get channel. If I have the channel, update its keep alive
        # channel_recv_peer = servicer_client.replace("ipv4:", "tcp://")

        # logger.info(f"Receive ping from: {channel_recv_peer}")
        # if channel_recv_peer not in self.channel_map:
        #     return custom_data_in  # I didn't open a channel to it, skip

        # channel = self.channel_map[channel_recv_peer]
        # s = self.rev_channel_map[channel]
        # self.channels[channel].update()

        # if channel not in self.channels:
        #     return custom_data_in  # I don't have any callbacks registered to it.

        # do something on heartbeat?
        return out

    def register_channel_service(
        self,
        channel: grpc.aio.Channel,
        channel_string: str,
        peer_id: bytes,
        async_callback: Callable,
        trigger: int,
        timeout_sec: float = 0,
    ) -> KeepAlive_Channel:

        assert async_callback is not None

        self.get_channel(channel_string)
        self.channels[channel_string].peer_id_assoc = peer_id

        logger.debug(f"KEEPALIVE - Register Channel Service: {channel_string}")
        if channel_string not in self.roundrobin_channels:  # tracking
            self.roundrobin_channels.append(channel_string)
        if trigger == TRIGGER_TIMEOUT:
            trigger = timeout_sec * 0.1 + 2  # type: ignore
        self.channels[channel_string].add_callbacks(trigger, async_callback)
        return self.channels[channel_string]

    async def keep_alive_task(self):
        logger.debug("KEEPALIVE - Keep Alive task running")
        counter = 0
        while True:
            if len(self.roundrobin_channels) == 0:
                await asyncio.sleep(
                    1
                )  # even keepalive delay for everyone... later can do something different.
                continue
            counter += 1
            if counter >= len(self.roundrobin_channels):
                counter = 0

            s = self.roundrobin_channels[counter]
            if self.channels[s].is_closed:
                # GONE!
                del self.channels[s]
                del self.roundrobin_channels[counter]
                continue

            if len(self.channels[s].callbacks) == 0:
                await asyncio.sleep(HEARTBEAT_INTERVAL / len(self.channels))
                continue

            if not (self.channels[s].is_due_for_heartbeat()):
                await asyncio.sleep(HEARTBEAT_INTERVAL / len(self.channels))
                continue

            # logger.debug(s)
            logger.debug(str(self.roundrobin_channels))
            asyncio.create_task(self.channels[s].heartbeat(True))  # heartbeat request.
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

Storage - sends all task data to engine.

Cache:
Open connection to OWNER / recent chain. When offline, send out value again (standard) - store only task
done. 

Event sender (this means that I also am an engine for a different task!!)
If timeout: Send out the requested task to network with ignore chain of old PEER. STORE


CHANGE: Cache also stores callable. This allows cache to spawn tasks!
"""
