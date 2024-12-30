######
# OLD -- not needed??? Put it in the Plugboard... as it is just a DHT
######


# Class for code for the servicer
# Class for client

import asyncio
import logging

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

    async def Bootstrap(
        self, peerID_to: bytes, transport_to: StarAddress
    ) -> list[pb_base.Bootstrap_Item]:
        logger.debug(f"Create Bootstrap Request for {peerID_to.hex()}")
        req = pb_base.Bootstrap_Request(
            peerID=self.peer_id, dial_from=self.transport.to_pb()
        )

        channel = transport_to.get_channel()
        self.stub = pb.PeerServiceStub(channel)  # connect to the other peer. Not local!
        recv = await self.stub.Bootstrap(req)
        await channel.close()
        return recv.value


class PeerService(pb.PeerServiceServicer):
    def __init__(self, internal_callback: "PlugBoard", my_addr):
        self.internal_callback = internal_callback
        self.addr = my_addr

    async def Bootstrap(
        self, request: pb_base.Bootstrap_Request, context: grpc.aio.ServicerContext
    ):
        peerID = request.peerID
        transport_address = StarAddress.from_pb(request.dial_from)
        logger.debug(f"Got Bootstrap Request from {peerID.hex()}")
        await self.internal_callback.add_peer(peerID, transport_address)

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
