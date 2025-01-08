# Class for code for the servicer
# Class for client

import asyncio
import logging
import time

import grpc
from . import main_pb2 as pb_base
from . import main_pb2_grpc as pb
from ..core.star_components import Event, StarAddress, StarProcess, StarTask

try:
    from src.plugboard import PlugBoard  # For typing purposes.
except:
    pass

logger = logging.getLogger(__name__)


class KeepAliveComm:
    # Sends requests to network.
    def __init__(self, channel: grpc.aio.Channel):
        self.stub = pb.KeepAliveServiceStub(channel)

    async def SendPing(self, timeout=0.2):
        request = pb_base.PING(value=int(time.time()))
        response = await self.stub.SendPing(request, timeout=timeout)
        return abs(time.time() - response) < 2

    async def SendHeartbeat(self, custom_data, timeout=0.2):
        request = pb_base.PING(value=int(time.time()))
        response = await self.stub.Heartbeat(
            request, timeout=timeout
        )  # send my heartbeat to peer
        return response


class KeepAliveCommService(pb.TaskServiceServicer):
    def __init__(self, internal_callback: "PlugBoard", my_addr):
        self.internal_callback = internal_callback
        self.addr = my_addr

    async def SendPing(
        self,
        request: pb_base.PING,
        context: grpc.aio.ServicerContext,
    ) -> pb_base.PONG:
        pass

    async def SendHeartbeat(
        self,
        request: pb_base.Heartbeat_Request,
        context: grpc.aio.ServicerContext,
    ) -> pb_base.Heartbeat_Response:
        pass
