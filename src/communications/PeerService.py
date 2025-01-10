# Class for code for the servicer
# Class for client

import asyncio
import logging

from src.KeepAlive import KeepAlive_Management

logger = logging.getLogger(__name__)

import grpc

try:
    from src.plugboard import PlugBoard  # For typing purposes.
except:
    pass
from . import main_pb2 as pb_base
from . import main_pb2_grpc as pb
from ..core.star_components import StarAddress


class PeerDiscoveryClient:
    # Sends requests to network.
    def __init__(self, my_addr: bytes, transport: StarAddress):
        self.transport = transport
        self.peer_id = my_addr
        self.kp: KeepAlive_Management = self.transport.keep_alive

    async def Bootstrap(
        self, peerID_to: bytes, transport_to: StarAddress, timeout=0.2
    ) -> list[pb_base.Bootstrap_Item]:
        logger.debug(f"Create Bootstrap Request for {peerID_to.hex()}")
        req = pb_base.Bootstrap_Request(
            peerID=self.peer_id, dial_from=self.transport.to_pb()
        )

        channel = transport_to.get_channel()
        channel_kp = self.kp.get_kp_channel(transport_to, peerID_to)
        self.stub = pb.PeerServiceStub(channel)  # connect to the other peer. Not local!

        try:
            recv = await self.stub.Bootstrap(req)
        except Exception as e:
            logger.debug(f"Deletion notice error")
            await channel_kp.kill_update()
            return []

        channel_kp.update()
        # await channel.close()
        return recv.value


class PeerService(pb.PeerServiceServicer):
    def __init__(self, internal_callback: "PlugBoard", my_addr, keep_alive):
        self.internal_callback = internal_callback
        self.addr = my_addr
        self.keep_alive = keep_alive

    async def Bootstrap(
        self, request: pb_base.Bootstrap_Request, context: grpc.aio.ServicerContext
    ):

        peerID = request.peerID
        transport_address = StarAddress.from_pb(request.dial_from)
        logger.debug(f"Got Bootstrap Request from {peerID.hex()}")
        await self.internal_callback.add_peer(peerID, transport_address)

        # peer_address = context.peer()
        # await self.keep_alive.receive_ping(peer_address)

        peers = self.internal_callback.peer_table.fetch_copy()
        out = pb_base.Bootstrap_Response()
        for peer, val in peers.items():
            # key: bytes
            # value: StarAddress in bytes
            out.value.append(
                pb_base.Bootstrap_Item(
                    peer_id=peer, addr=StarAddress.from_bytes(val).to_pb()
                )
            )
        return out
