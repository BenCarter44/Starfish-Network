# Class for code for the servicer
# Class for client

import asyncio
import logging
import time

import dill
import grpc


from . import main_pb2 as pb_base
from . import main_pb2_grpc as pb
from ..core.star_components import Event, StarAddress, StarProcess, StarTask

try:
    from src.plugboard import PlugBoard  # For typing purposes.
except:
    pass

logger = logging.getLogger(__name__)

PING_TIMEOUT = 0.3


class KeepAliveComm:
    # Sends requests to network.
    def __init__(self, channel: grpc.aio.Channel):
        self.stub = pb.KeepAliveServiceStub(channel)

    async def SendPing(self, timeout=PING_TIMEOUT):
        logger.debug(f"KEEPALIVE - SendPing Request")
        request = pb_base.PING(value=int(time.time()))
        response = await self.stub.SendPing(request, timeout=timeout)
        return abs(time.time() - response) < 2

    async def SendHeartbeat(self, custom_data, timeout=PING_TIMEOUT):
        # logger.debug("Send Heartbeat Request")
        request = pb_base.Heartbeat_Request(custom_data=dill.dumps(custom_data))
        try:
            response = await self.stub.SendHeartbeat(
                request, timeout=timeout
            )  # send my heartbeat to peer
        except Exception as e:
            logger.debug(f"KEEPALIVE - SendHeartbeat error")
            return False
        return dill.loads(response.custom_data)


class KeepAliveCommService(pb.KeepAliveServiceServicer):
    def __init__(
        self,
        internal_callback: "PlugBoard",
        my_addr,
        keep_alive,  # type: src.KeepAlive
    ):
        self.internal_callback = internal_callback
        self.addr = my_addr
        self.keep_alive = keep_alive

    async def SendPing(
        self,
        request: pb_base.PING,
        context: grpc.aio.ServicerContext,
    ) -> pb_base.PONG:
        logger.debug(f"KEEPALIVE - Recv Ping Request")
        # peer_address = context.peer()
        # await self.keep_alive.receive_ping(peer_address)
        return pb_base.PONG(value=int(time.time()))

    async def SendHeartbeat(
        self,
        request: pb_base.Heartbeat_Request,
        context: grpc.aio.ServicerContext,
    ) -> pb_base.Heartbeat_Response:
        # logger.debug("Recv Heartbeat Request")

        data_in = dill.loads(request.custom_data)

        data_out = await self.keep_alive.receive_heartbeat_service(data_in)
        return pb_base.Heartbeat_Response(custom_data=dill.dumps(data_out))
