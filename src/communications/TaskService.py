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
        request = pb_base.SendEvent_Request(evt=event, who=self.peer_id)
        response = await self.stub.SendEvent(request, timeout=timeout)
        self.kp_channel.update()
        return response

    async def SendMonitor_Request(
        self, proc: StarProcess, my_addr: bytes, task: StarTask, timeout=0.4
    ):
        proc_data = proc.to_bytes()
        request = pb_base.SendMonitor_Request(
            process_data=proc_data, who=my_addr, task=task.to_pb(include_callable=True)
        )
        response = await self.stub.SendMonitorRequest(request, timeout=timeout)
        self.kp_channel.update()
        return response

    async def SendCheckpoint(
        self,
        proc: bytes,
        event_origin: Event | None,
        event_to: Event,
        addr_of_engine: bytes,
        timeout=0.4,
    ):
        proc_data = proc
        if event_origin is None:
            event_origin_bytes = b""
        else:
            event_origin_bytes = event_origin.to_bytes()

        request = pb_base.SendCheckpoint_Request(
            process_data=proc_data,
            who=addr_of_engine,
            event_origin=event_origin_bytes,
            event_to=event_to.to_bytes(),
        )
        response = await self.stub.SendCheckpoint(request, timeout=timeout)
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

        # Check-in to monitor -- ALWAYS SEND.... Change later to checkpoint events
        logger.debug(evt.origin)
        logger.debug(evt)
        await self.internal_callback.send_checkpoint(
            evt.target.get_process_id(), evt.origin, evt
        )

        if peerID == self.addr:
            # It's to me!
            remaining = self.internal_callback.receive_event(evt)
            return pb_base.SendEvent_Response(
                status=pb_base.DHTStatus.OWNED, remaining=remaining, who=self.addr
            )

        # It is NOT to me!

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

    async def SendMonitorRequest(
        self,
        request: pb_base.SendMonitor_Request,
        context: grpc.aio.ServicerContext,
    ) -> pb_base.SendMonitor_Response:

        proc = StarProcess.from_bytes(request.process_data)
        who = request.who
        task = StarTask.from_pb(request.task)

        await self.internal_callback.receive_monitor_request(proc, who, task)

        return pb_base.SendMonitor_Response(status=pb_base.DHTStatus.FOUND)

    async def SendCheckpoint(
        self,
        request: pb_base.SendCheckpoint_Request,
        context: grpc.aio.ServicerContext,
    ) -> pb_base.SendCheckpoint_Response:

        proc = request.process_data
        who = request.who
        event_origin = request.event_origin

        if request.event_origin == b"":
            event_origin = None
        else:
            event_origin = Event.from_bytes(event_origin)

        event_to = request.event_to

        await self.internal_callback.receive_checkpoint(
            proc, who, event_origin, Event.from_bytes(event_to)
        )

        return pb_base.SendCheckpoint_Response(status=pb_base.DHTStatus.FOUND)
