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
    def __init__(self, transport: StarAddress, my_addr: bytes):
        channel = transport.get_channel()
        kp = transport.keep_alive
        self.kp_channel = kp.get_kp_channel(transport, my_addr)

        self.stub = pb.TaskServiceStub(channel)
        self.peer_id = my_addr

    async def SendEvent(self, evt: Event, timeout=0.4) -> pb_base.SendEvent_Response:
        event = evt.to_pb()
        request = pb_base.SendEvent_Request(evt=event)
        response = await self.stub.SendEvent(request, timeout=timeout)
        self.kp_channel.update()
        return response


class TaskService(pb.TaskServiceServicer):
    def __init__(self, internal_callback: "PlugBoard", my_addr, keep_alive):
        self.internal_callback = internal_callback
        self.addr = my_addr
        self.keep_alive = keep_alive

    async def SendEvent(
        self,
        request: pb_base.SendEvent_Request,
        context: grpc.aio.ServicerContext,
    ) -> pb_base.SendEvent_Response:

        # use internal callback. Search DHT.
        evt = Event.from_pb(request.evt)

        task: StarTask = evt.target

        logger.debug("Get task owner")

        # peer_address = context.peer()
        # await self.keep_alive.receive_ping(peer_address)

        peerID: bytes = await self.internal_callback.get_task_owner(task)
        logger.debug(f"Task: {task.get_id().hex()} OWNED by {peerID.hex()}")

        if peerID == self.addr:
            # It's to me!
            remaining = self.internal_callback.receive_event(evt)
            return pb_base.SendEvent_Response(
                status=pb_base.DHTStatus.OWNED, remaining=remaining, who=self.addr
            )

        # Send to peer that owns the task!
        tp = await self.internal_callback.get_peer_transport(peerID)
        if tp is None:
            logger.info(f"Transport for {peerID.hex()} not found!")
            return pb_base.SendEvent_Response(
                status=pb_base.DHTStatus.NOT_FOUND, remaining=0
            )

        taskClient = TaskPeer(tp, peerID)
        try:
            response = await taskClient.SendEvent(evt, timeout=0.4)
        except Exception as e:
            logger.warning(f"Transport for {peerID.hex()} timeout {e}")
            return pb_base.SendEvent_Response(
                pb_base.DHTStatus.ERR, remaining=0, who=peerID
            )

        # await channel.close()
        return pb_base.SendEvent_Response(
            status=pb_base.DHTStatus.FOUND,
            remaining=response.remaining,
            who=response.who,
        )
