# Class for code for the servicer
# Class for client

import asyncio
import logging
import sys

import dill
import grpc

#
from . import main_pb2 as pb_base
from . import main_pb2_grpc as pb
from ..core.star_components import Event, StarAddress, StarProcess, StarTask

try:
    from src.plugboard import PlugBoard  # For typing purposes.
except:
    pass
try:
    from src.core.io_host import Device
except:
    pass

logger = logging.getLogger(__name__)

DEVICE_TIMEOUT = 1


class IOClient:
    # Sends requests to network.
    def __init__(
        self,
        transport: StarAddress,
        addr: bytes,
        process_id: bytes,
    ):
        channel = transport.get_channel()
        kp = transport.keep_alive
        self.kp_channel = kp.get_kp_channel(transport, addr)

        self.stub = pb.IOServiceStub(channel)
        self.peer_id = addr
        self.process_id = process_id

    async def OpenDevice(self, device: Device, timeout=DEVICE_TIMEOUT):
        logger.info(f"IO - OpenDevice request {device.get_name()}")
        dev_id = device.get_id()

        dreq = pb_base.DeviceRequest(
            device_id=dev_id,
            process_id=self.process_id,
            request_type=pb_base.UPDATE_TYPE.OPEN_DEV,
        )
        try:
            resp = await self.stub.OpenDevice(dreq, timeout=timeout)
        except:
            logger.warning("IO - Error on stub send")
            await self.kp_channel.kill_update()
            return b"", pb_base.DHTStatus.ERR
        await self.kp_channel.update()
        return resp.local_device_identifier, resp.status

    async def CloseDevice(self, device, timeout=DEVICE_TIMEOUT):
        logger.info(f"IO - CloseDevice request {device.get_name()}")
        dreq = pb_base.DeviceRequest(
            device_id=device.get_id(),
            process_id=device.get_local_device_identifier(),
            request_type=pb_base.UPDATE_TYPE.CLOSE_DEV,
        )
        try:
            resp = await self.stub.CloseDevice(dreq, timeout=timeout)
        except:
            logger.warning("IO - Error on stub send")
            await self.kp_channel.kill_update()
            return pb_base.DHTStatus.ERR
        await self.kp_channel.update()
        return resp.status

    async def UnmountDevice(self, device, timeout=DEVICE_TIMEOUT):
        logger.info(f"IO - UnmountDevice request {device.get_name()}")
        dreq = pb_base.DeviceRequest(
            device_id=device.get_id(),
            process_id=self.process_id,
            request_type=pb_base.UPDATE_TYPE.UNMOUNT,
        )
        try:
            resp = await self.stub.UnmountDevice(dreq, timeout=timeout)
        except:
            logger.warning("IO - Error on stub send")
            await self.kp_channel.kill_update()
            return pb_base.DHTStatus.ERR
        await self.kp_channel.update()
        return resp.status

    async def ReadDevice(self, device, number_of_bytes: int, timeout=DEVICE_TIMEOUT):
        logger.info(f"IO - ReadDevice request {device.get_name()}")
        dreq = pb_base.DataRequest(
            device_id=device.get_id(),
            local_device_identifier=device.get_local_device_identifier(),
            request_type=pb_base.UPDATE_TYPE.READ_DEV,
            data=b"",
            field1=number_of_bytes,
        )
        try:
            resp = await self.stub.ReadDevice(dreq, timeout=timeout)
        except:
            logger.warning("IO - Error on stub send")
            await self.kp_channel.kill_update()
            return b"", pb_base.DHTStatus.ERR
        await self.kp_channel.update()
        return resp.data, resp.status

    async def WriteDevice(self, device: Device, data, timeout=DEVICE_TIMEOUT):
        logger.info(f"IO - WriteDevice request {device.get_name()}")
        dreq = pb_base.DataRequest(
            device_id=device.get_id(),
            local_device_identifier=device.get_local_device_identifier(),
            request_type=pb_base.UPDATE_TYPE.WRITE_DEV,
            data=data,
            field1=0,
        )
        try:
            resp = await self.stub.WriteDevice(dreq, timeout=timeout)
        except:
            logger.warning("IO - Error on stub send")
            await self.kp_channel.kill_update()
            return pb_base.DHTStatus.ERR
        return resp.status

    async def ReadAvailable(self, device, timeout=DEVICE_TIMEOUT):
        logger.info(f"IO - ReadAvailable request {device.get_name()}")
        dreq = pb_base.DataRequest(
            device_id=device.get_id(),
            local_device_identifier=device.get_local_device_identifier(),
            request_type=pb_base.UPDATE_TYPE.READ_AVAILABLE,
            data=b"",
            field1=0,
        )
        try:
            resp = await self.stub.ReadAvailable(dreq, timeout=timeout)
        except:
            logger.warning("IO - Error on stub send")
            await self.kp_channel.kill_update()
            return 0, pb_base.DHTStatus.ERR
        await self.kp_channel.update()
        return resp.field1, resp.status


class IOService(pb.IOServiceServicer):
    def __init__(self, plugboard_callback: "PlugBoard"):
        self.plugboard_callback = plugboard_callback

    async def OpenDevice(
        self, request: pb_base.DeviceRequest, context: grpc.aio.ServicerContext
    ) -> pb_base.DeviceResponse:

        if request.request_type != pb_base.UPDATE_TYPE.OPEN_DEV:
            return pb_base.DeviceResponse(
                device_id=request.device_id,
                local_device_identifier=b"",
                status=pb_base.DHTStatus.ERR,
            )

        device = Device.from_id(request.device_id)
        result_id, status = await self.plugboard_callback.open_device(
            device, request.process_id
        )

        return pb_base.DeviceResponse(
            device_id=request.device_id,
            local_device_identifier=result_id,
            status=status,
        )

    async def CloseDevice(
        self, request: pb_base.DeviceRequest, context: grpc.aio.ServicerContext
    ) -> pb_base.DeviceResponse:

        if request.request_type != pb_base.UPDATE_TYPE.CLOSE_DEV:
            return pb_base.DeviceResponse(
                device_id=request.device_id,
                local_device_identifier=b"",
                status=pb_base.DHTStatus.ERR,
            )
        device = Device.from_id(request.device_id)
        device.set_local_id(request.process_id)
        result = await self.plugboard_callback.close_device(device)
        return pb_base.DeviceResponse(
            device_id=request.device_id,
            local_device_identifier=b"",
            status=result,
        )

    async def UnmountDevice(
        self, request: pb_base.DeviceRequest, context: grpc.aio.ServicerContext
    ) -> pb_base.DeviceResponse:

        if request.request_type != pb_base.UPDATE_TYPE.UNMOUNT:
            return pb_base.DeviceResponse(
                device_id=request.device_id,
                local_device_identifier=b"",
                status=pb_base.DHTStatus.ERR,
            )

        device = Device.from_id(request.device_id)
        result = await self.plugboard_callback.unmount_device(device)
        return pb_base.DeviceResponse(
            device_id=request.device_id,
            local_device_identifier=b"",
            status=result,
        )

    async def ReadDevice(
        self, request: pb_base.DataRequest, context: grpc.aio.ServicerContext
    ) -> pb_base.DataResponse:

        if request.request_type != pb_base.UPDATE_TYPE.READ_DEV:
            return pb_base.DataResponse(
                device_id=request.device_id,
                local_device_identifier=b"",
                status=pb_base.DHTStatus.ERR,
                field1=0,
            )

        device = Device.from_id(request.device_id)
        device.set_local_id(request.local_device_identifier)
        data, status = await self.plugboard_callback.read_device(
            device, request.field1
        )  # length
        return pb_base.DataResponse(
            device_id=device.get_id(),
            local_device_identifier=device.get_local_device_identifier(),
            data=data,
            field1=0,
            status=status,
        )

    async def WriteDevice(
        self, request: pb_base.DataRequest, context: grpc.aio.ServicerContext
    ) -> pb_base.DataResponse:
        logger.info("IO - Received Writer req")
        if request.request_type != pb_base.UPDATE_TYPE.WRITE_DEV:
            return pb_base.DataResponse(
                device_id=request.device_id,
                local_device_identifier=b"",
                status=pb_base.DHTStatus.ERR,
                field1=0,
            )

        device = Device.from_id(request.device_id)
        device.set_local_id(request.local_device_identifier)
        data = request.data
        status = await self.plugboard_callback.write_device(device, data)  # length
        return pb_base.DataResponse(
            device_id=device.get_id(),
            local_device_identifier=device.get_local_device_identifier(),
            data=b"",
            field1=0,
            status=status,
        )

    async def ReadAvailable(
        self, request: pb_base.DataRequest, context: grpc.aio.ServicerContext
    ) -> pb_base.DataResponse:
        if request.request_type != pb_base.UPDATE_TYPE.READ_AVAILABLE:
            return pb_base.DataResponse(
                device_id=request.device_id,
                local_device_identifier=b"",
                status=pb_base.DHTStatus.ERR,
                field1=0,
            )

        device = Device.from_id(request.device_id)
        device.set_local_id(request.local_device_identifier)
        number, status = await self.plugboard_callback.read_available(device)  # length
        return pb_base.DataResponse(
            device_id=device.get_id(),
            local_device_identifier=device.get_local_device_identifier(),
            data=b"",
            field1=number,
            status=status,
        )
