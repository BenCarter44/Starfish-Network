# Class for code for the servicer
# Class for client

import asyncio
import logging

import grpc
from . import main_pb2 as pb_base
from . import main_pb2_grpc as pb
from ..core.star_components import Event, StarAddress, StarProcess, StarTask

try:
    from src.plugboard import PlugBoard  # For typing purposes.
except:
    pass

logger = logging.getLogger(__name__)


class TaskPeer:
    # Sends requests to network.
    def __init__(self, channel: grpc.aio.Channel, my_addr: bytes):
        self.stub = pb.TaskServiceStub(channel)
        self.peer_id = my_addr

    async def SendEvent(self, evt: Event) -> pb_base.DHTStatus:
        event = evt.to_pb()
        request = pb_base.SendEvent_Request(evt=event)
        response = await self.stub.SendEvent(request)
        return response


class TaskService(pb.TaskServiceServicer):
    def __init__(self, internal_callback: "PlugBoard", my_addr):
        self.internal_callback = internal_callback
        self.addr = my_addr

    async def SendEvent(
        self,
        request: pb_base.SendEvent_Request,
        context: grpc.aio.ServicerContext,
    ) -> pb_base.SendEvent_Response:

        # use internal callback. Search DHT.
        evt = Event.from_pb(request.evt)

        task: StarTask = evt.target

        logger.debug("Get task owner")
        peerID: bytes = await self.internal_callback.get_task_owner(task)
        logger.debug(f"Task: {task.get_id().hex()} OWNED by {peerID.hex()}")

        if peerID == self.addr:
            # It's to me!
            self.internal_callback.receive_event(evt)
            return pb_base.SendEvent_Response(status=pb_base.DHTStatus.OWNED)

        # Send to peer that owns the task!
        tp = await self.internal_callback.get_peer_transport(peerID)
        if tp is None:
            logger.info(f"Transport for {peerID.hex()} not found!")
            return pb_base.SendEvent_Response(status=pb_base.DHTStatus.NOT_FOUND)

        channel = tp.get_channel()
        taskClient = TaskPeer(channel, self.addr)
        response = await taskClient.SendEvent(evt)
        await channel.close()
        return pb_base.SendEvent_Response(status=pb_base.DHTStatus.FOUND)
