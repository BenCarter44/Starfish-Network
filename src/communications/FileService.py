# Class for code for the servicer
# Class for client

import asyncio
import logging

import grpc

from src.core.File import HostedFile
from . import main_pb2 as pb_base
from . import main_pb2_grpc as pb
from ..core.star_components import Event, StarAddress, StarProcess, StarTask

try:
    from src.plugboard import PlugBoard  # For typing purposes.
except:
    pass

logger = logging.getLogger(__name__)


class FileClient:
    # Sends requests to network.
    def __init__(self, transport: StarAddress, my_addr: bytes, process_id: bytes):
        channel = transport.get_channel()
        kp = transport.keep_alive
        self.kp_channel = kp.get_kp_channel(transport, my_addr)

        self.stub = pb.FileServiceStub(channel)
        self.peer_id = my_addr
        self.process_id = process_id

    # Used by DHT
    # async def CreateFile(self, file: HostedFile, timeout=0.4):
    #    pass

    # async def CreateFile(self, file: HostedFile, timeout=0.4):
    #     key = file.get_key()
    #     local_identifier = b""

    #     file_req = pb_base.FILE_REQUEST.CREATE
    #     request = pb_base.FileServiceRequest(
    #         local_file_identifier=local_identifier,
    #         key=key,
    #         file_request=file_req,
    #         data=self.process_id,
    #         process_id=self.process_id,
    #     )
    #     response = await self.stub.CreateFile(request, timeout=timeout)
    #     self.kp_channel.update()
    #     return response.data

    async def OpenFile(self, file: HostedFile, timeout=0.4):
        logger.info(
            f"FILE - OpenFile request: {file.get_key().hex()} - {file.local_identifier.hex()}"
        )
        key = file.get_key()
        local_identifier = b""

        file_req = pb_base.FILE_REQUEST.OPEN
        request = pb_base.FileServiceRequest(
            local_file_identifier=local_identifier,
            key=key,
            file_request=file_req,
            data=self.process_id,
            process_id=self.process_id,
        )
        response = await self.stub.OpenFile(request, timeout=timeout)
        self.kp_channel.update()
        return response.data

    async def ReadFile(self, file: HostedFile, length: int = -1, timeout=0.4):
        logger.info(
            f"FILE - ReadFile request: {file.get_key().hex()} - {file.local_identifier.hex()}"
        )
        data = int.to_bytes(length, 4, "big", signed=True)
        key = file.get_key()
        local_identifier = file.get_local_identifier()

        file_req = pb_base.FILE_REQUEST.READ
        request = pb_base.FileServiceRequest(
            local_file_identifier=local_identifier,
            key=key,
            file_request=file_req,
            data=data,
            process_id=self.process_id,
        )
        response = await self.stub.ReadFile(request, timeout=timeout)
        self.kp_channel.update()
        return response.data

    async def WriteFile(self, file: HostedFile, data: bytes, timeout=0.4):
        logger.info(
            f"FILE - WriteFile request: {file.get_key().hex()} - {file.local_identifier.hex()}"
        )
        key = file.get_key()
        local_identifier = file.get_local_identifier()

        file_req = pb_base.FILE_REQUEST.WRITE
        request = pb_base.FileServiceRequest(
            local_file_identifier=local_identifier,
            key=key,
            file_request=file_req,
            data=data,
            process_id=self.process_id,
        )
        response = await self.stub.WriteFile(request, timeout=timeout)
        self.kp_channel.update()
        return response.data

    async def SeekFile(self, file: HostedFile, seek: int, start: int, timeout=0.4):
        logger.info(
            f"FILE - SeekFile request: {file.get_key().hex()} - {file.local_identifier.hex()}"
        )
        key = file.get_key()
        local_identifier = file.get_local_identifier()
        data = int.to_bytes(seek, 4, "big")
        data += int.to_bytes(start, 4, "big")

        file_req = pb_base.FILE_REQUEST.SEEK
        request = pb_base.FileServiceRequest(
            local_file_identifier=local_identifier,
            key=key,
            file_request=file_req,
            data=data,
            process_id=self.process_id,
        )
        response = await self.stub.SeekFile(request, timeout=timeout)
        self.kp_channel.update()
        return response.data

    async def TellFile(self, file: HostedFile, timeout=0.4):
        logger.info(
            f"FILE - TellFile request: {file.get_key().hex()} - {file.local_identifier.hex()}"
        )
        key = file.get_key()
        local_identifier = file.get_local_identifier()

        file_req = pb_base.FILE_REQUEST.SEEK
        request = pb_base.FileServiceRequest(
            local_file_identifier=local_identifier,
            key=key,
            file_request=file_req,
            data=b"",
            process_id=self.process_id,
        )
        response = await self.stub.TellFile(request, timeout=timeout)
        self.kp_channel.update()
        out = int.from_bytes(response.data, "big")
        return out

    async def CloseFile(self, file: HostedFile, timeout=0.4):
        logger.info(
            f"FILE - CloseFile request: {file.get_key().hex()} - {file.local_identifier.hex()}"
        )
        data = b""
        key = file.get_key()
        local_identifier = file.get_local_identifier()

        file_req = pb_base.FILE_REQUEST.CLOSE
        request = pb_base.FileServiceRequest(
            local_file_identifier=local_identifier,
            key=key,
            file_request=file_req,
            data=data,
            process_id=self.process_id,
        )
        response = await self.stub.CloseFile(request, timeout=timeout)
        self.kp_channel.update()
        return response.status


class FileService(pb.FileServiceServicer):
    def __init__(self, internal_callback: "PlugBoard", my_addr, keep_alive):
        self.internal_callback = internal_callback
        self.addr = my_addr
        self.keep_alive = keep_alive

    # async def CreateFile(
    #     self, request: pb_base.FileServiceRequest, context: grpc.aio.ServicerContext
    # ) -> pb_base.FileServiceResponse:
    #     key = request.key
    #     local_file_identifier = request.local_file_identifier

    #     if request.file_request != pb_base.FILE_REQUEST.CLOSE:
    #         return pb_base.FileServiceResponse(status=pb_base.DHTStatus.ERR, data=b"")

    #     try:
    #         f = self.internal_callback.fetch_file(key, local_file_identifier)
    #     except:
    #         return pb_base.FileServiceResponse(
    #             status=pb_base.DHTStatus.NOT_FOUND, data=b""
    #         )

    #     f.create()  # idempotent

    #     return pb_base.FileServiceResponse(status=pb_base.DHTStatus.OK, data=b"")

    async def OpenFile(
        self, request: pb_base.FileServiceRequest, context: grpc.aio.ServicerContext
    ) -> pb_base.FileServiceResponse:
        key = request.key
        local_file_identifier = request.local_file_identifier

        logger.info(
            f"FILE - OpenFile request recv: {key.hex()} - {local_file_identifier.hex()}"
        )

        if request.file_request != pb_base.FILE_REQUEST.OPEN:
            return pb_base.FileServiceResponse(status=pb_base.DHTStatus.ERR, data=b"")

        try:
            f = await self.internal_callback.fetch_file(
                key, local_file_identifier, request.process_id
            )
        except ValueError:
            return pb_base.FileServiceResponse(
                status=pb_base.DHTStatus.NOT_FOUND, data=b""
            )

        f.open()  # idempotent

        return pb_base.FileServiceResponse(
            status=pb_base.DHTStatus.OK, data=f.get_local_identifier()
        )

    async def ReadFile(
        self, request: pb_base.FileServiceRequest, context: grpc.aio.ServicerContext
    ) -> pb_base.FileServiceResponse:

        key = request.key
        local_file_identifier = request.local_file_identifier

        logger.info(
            f"FILE - ReadFile request recv: {key.hex()} - {local_file_identifier.hex()}"
        )

        if request.file_request != pb_base.FILE_REQUEST.READ:
            return pb_base.FileServiceResponse(status=pb_base.DHTStatus.ERR, data=b"")

        try:
            f: HostedFile = await self.internal_callback.fetch_file(
                key, local_file_identifier
            )
        except:
            return pb_base.FileServiceResponse(
                status=pb_base.DHTStatus.NOT_FOUND, data=b""
            )

        length = int.from_bytes(request.data, "big", signed=True)
        f.open()  # idempotent
        out = f.read(length)

        return pb_base.FileServiceResponse(status=pb_base.DHTStatus.OK, data=out)

    async def WriteFile(
        self, request: pb_base.FileServiceRequest, context: grpc.aio.ServicerContext
    ) -> pb_base.FileServiceResponse:
        key = request.key
        local_file_identifier = request.local_file_identifier

        logger.info(
            f"FILE - WriteFile request recv: {key.hex()} - {local_file_identifier.hex()}"
        )

        if request.file_request != pb_base.FILE_REQUEST.WRITE:
            return pb_base.FileServiceResponse(status=pb_base.DHTStatus.ERR, data=b"")

        logger.debug(f"FILE - Writer check 1")
        try:
            f: HostedFile = await self.internal_callback.fetch_file(
                key, local_file_identifier
            )
        except ValueError:
            logger.debug(f"FILE - Writer check 2 error")
            return pb_base.FileServiceResponse(
                status=pb_base.DHTStatus.NOT_FOUND, data=b""
            )

        # f.open()  # idempotent
        f.write(request.data)

        return pb_base.FileServiceResponse(status=pb_base.DHTStatus.OK, data=b"")

    async def SeekFile(
        self, request: pb_base.FileServiceRequest, context: grpc.aio.ServicerContext
    ) -> pb_base.FileServiceResponse:
        key = request.key
        local_file_identifier = request.local_file_identifier

        logger.info(
            f"FILE - SeekFile request recv: {key.hex()} - {local_file_identifier.hex()}"
        )

        if request.file_request != pb_base.FILE_REQUEST.SEEK:
            return pb_base.FileServiceResponse(status=pb_base.DHTStatus.ERR, data=b"")

        try:
            f: HostedFile = await self.internal_callback.fetch_file(
                key, local_file_identifier
            )
        except:
            return pb_base.FileServiceResponse(
                status=pb_base.DHTStatus.NOT_FOUND, data=b""
            )

        offset = int.from_bytes(request.data[:4], "big")
        whence = int.from_bytes(request.data[4:], "big")

        # f.open()  # idempotent
        f.seek(offset, whence)

        return pb_base.FileServiceResponse(status=pb_base.DHTStatus.OK, data=b"")

    async def TellFile(
        self, request: pb_base.FileServiceRequest, context: grpc.aio.ServicerContext
    ) -> pb_base.FileServiceResponse:
        key = request.key
        local_file_identifier = request.local_file_identifier

        logger.info(
            f"FILE - TellFile request recv: {key.hex()} - {local_file_identifier.hex()}"
        )

        if request.file_request != pb_base.FILE_REQUEST.TELL:
            return pb_base.FileServiceResponse(status=pb_base.DHTStatus.ERR, data=b"")

        try:
            f: HostedFile = await self.internal_callback.fetch_file(
                key, local_file_identifier
            )
        except:
            return pb_base.FileServiceResponse(
                status=pb_base.DHTStatus.NOT_FOUND, data=b""
            )

        # f.open()  # idempotent
        position = f.tell()

        return pb_base.FileServiceResponse(
            status=pb_base.DHTStatus.OK, data=position.to_bytes(4, "big")
        )

    async def CloseFile(
        self, request: pb_base.FileServiceRequest, context: grpc.aio.ServicerContext
    ) -> pb_base.FileServiceResponse:
        key = request.key
        local_file_identifier = request.local_file_identifier

        logger.info(
            f"FILE - CloseFile request recv: {key.hex()} - {local_file_identifier.hex()}"
        )

        if request.file_request != pb_base.FILE_REQUEST.CLOSE:
            return pb_base.FileServiceResponse(status=pb_base.DHTStatus.ERR, data=b"")

        try:
            f: HostedFile = await self.internal_callback.fetch_file(
                key, local_file_identifier
            )
        except:
            return pb_base.FileServiceResponse(
                status=pb_base.DHTStatus.NOT_FOUND, data=b""
            )

        f.close()
        self.internal_callback.close_file(key, local_file_identifier)

        return pb_base.FileServiceResponse(status=pb_base.DHTStatus.OK, data=b"")
