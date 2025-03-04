# Class for code for the servicer
# Class for client

import asyncio
import logging

import dill
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

FILE_REQ_TIMEOUT = 2


class FileClient:
    # Sends requests to network.
    def __init__(
        self,
        transport: StarAddress,
        my_addr: bytes,
        process_id: bytes,
        is_monitor=False,
    ):
        channel = transport.get_channel()
        kp = transport.keep_alive
        self.kp_channel = kp.get_kp_channel(transport, my_addr)

        self.stub = pb.FileServiceStub(channel)
        self.peer_id = my_addr
        self.process_id = process_id
        self.is_monitor = is_monitor

    # Used by DHT
    # async def CreateFile(self, file: HostedFile, timeout=FILE_REQ_TIMEOUT):
    #    pass

    # async def CreateFile(self, file: HostedFile, timeout=FILE_REQ_TIMEOUT):
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

    async def OpenFile(self, file: HostedFile, timeout=FILE_REQ_TIMEOUT):
        logger.info(
            f"FILE - OpenFile request: {file.get_key().hex()} - {file.local_identifier.hex()} {self.is_monitor}"
        )
        key = file.get_key()
        local_identifier = file.local_identifier

        skmt = b"\x00"
        if self.is_monitor:
            skmt = b"\x01"

        file_req = pb_base.FILE_REQUEST.OPEN
        request = pb_base.FileServiceRequest(
            local_file_identifier=local_identifier,
            key=key,
            file_request=file_req,
            data=self.process_id,
            process_id=self.process_id,
            is_monitor=skmt,
        )
        try:
            response = await self.stub.OpenFile(request, timeout=timeout)
        except:
            logger.warning("FILE - Error on stub send")
            await self.kp_channel.kill_update()
            return b""
        await self.kp_channel.update()
        return response.data

    async def ReadFile(
        self, file: HostedFile, length: int = -1, timeout=FILE_REQ_TIMEOUT
    ):
        logger.info(
            f"FILE - ReadFile request: {file.get_key().hex()} - {file.local_identifier.hex()}"
        )
        data = int.to_bytes(length, 4, "big", signed=True)
        key = file.get_key()
        local_identifier = file.get_local_identifier()

        skmt = b"\x00"
        if self.is_monitor:
            skmt = b"\x01"

        file_req = pb_base.FILE_REQUEST.READ
        request = pb_base.FileServiceRequest(
            local_file_identifier=local_identifier,
            key=key,
            file_request=file_req,
            data=data,
            process_id=self.process_id,
            is_monitor=skmt,
        )
        try:
            response = await self.stub.ReadFile(request, timeout=timeout)
        except:
            logger.warning("FILE - Error on stub send")
            await self.kp_channel.kill_update()
            return b""
        await self.kp_channel.update()
        return response.data

    async def WriteFile(self, file: HostedFile, data: bytes, timeout=FILE_REQ_TIMEOUT):
        logger.info(
            f"FILE - WriteFile request: {file.get_key().hex()} - {file.local_identifier.hex()}"
        )
        key = file.get_key()
        local_identifier = file.get_local_identifier()

        skmt = b"\x00"
        if self.is_monitor:
            skmt = b"\x01"

        file_req = pb_base.FILE_REQUEST.WRITE
        request = pb_base.FileServiceRequest(
            local_file_identifier=local_identifier,
            key=key,
            file_request=file_req,
            data=data,
            process_id=self.process_id,
            is_monitor=skmt,
        )
        try:
            response = await self.stub.WriteFile(request, timeout=timeout)
        except:
            logger.warning("FILE - Error on stub send")
            await self.kp_channel.kill_update()
            return b""
        await self.kp_channel.update()
        return response.data

    async def SeekFile(
        self, file: HostedFile, seek: int, start: int, timeout=FILE_REQ_TIMEOUT
    ):
        logger.info(
            f"FILE - SeekFile request: {file.get_key().hex()} - {file.local_identifier.hex()}"
        )
        key = file.get_key()
        local_identifier = file.get_local_identifier()
        data = int.to_bytes(seek, 4, "big")
        data += int.to_bytes(start, 4, "big")

        skmt = b"\x00"
        if self.is_monitor:
            skmt = b"\x01"

        file_req = pb_base.FILE_REQUEST.SEEK
        request = pb_base.FileServiceRequest(
            local_file_identifier=local_identifier,
            key=key,
            file_request=file_req,
            data=data,
            process_id=self.process_id,
            is_monitor=skmt,
        )
        try:
            response = await self.stub.SeekFile(request, timeout=timeout)
        except:
            logger.warning("FILE - Error on stub send")
            await self.kp_channel.kill_update()
            return b""
        await self.kp_channel.update()
        return response.data

    async def TellFile(self, file: HostedFile, timeout=FILE_REQ_TIMEOUT):
        logger.info(
            f"FILE - TellFile request: {file.get_key().hex()} - {file.local_identifier.hex()}"
        )
        key = file.get_key()
        local_identifier = file.get_local_identifier()

        skmt = b"\x00"
        if self.is_monitor:
            skmt = b"\x01"

        file_req = pb_base.FILE_REQUEST.SEEK
        request = pb_base.FileServiceRequest(
            local_file_identifier=local_identifier,
            key=key,
            file_request=file_req,
            data=b"",
            process_id=self.process_id,
            is_monitor=skmt,
        )
        try:
            response = await self.stub.TellFile(request, timeout=timeout)
        except:
            logger.warning("FILE - Error on stub send")
            await self.kp_channel.kill_update()
            return 0
        await self.kp_channel.update()
        out = int.from_bytes(response.data, "big")
        return out

    async def CloseFile(self, file: HostedFile, timeout=FILE_REQ_TIMEOUT):
        logger.info(
            f"FILE - CloseFile request: {file.get_key().hex()} - {file.local_identifier.hex()}"
        )
        data = b""
        key = file.get_key()
        local_identifier = file.get_local_identifier()

        skmt = b"\x00"
        if self.is_monitor:
            skmt = b"\x01"

        file_req = pb_base.FILE_REQUEST.CLOSE
        request = pb_base.FileServiceRequest(
            local_file_identifier=local_identifier,
            key=key,
            file_request=file_req,
            data=data,
            process_id=self.process_id,
            is_monitor=skmt,
        )
        try:
            response = await self.stub.CloseFile(request, timeout=timeout)
        except:
            logger.warning("FILE - Error on stub send")
            await self.kp_channel.kill_update()
            return pb_base.DHTStatus.ERR

        await self.kp_channel.update()
        return response.status

    async def SendMonitorRequest(
        self, file: HostedFile, contents: bytes, who: bytes, timeout=FILE_REQ_TIMEOUT
    ):
        # assert isinstance(timeout, int)
        # assert isinstance(contents, bytes)
        logger.info(
            f"FILE - SendMonitor request: {file.get_key().hex()} - {file.local_identifier.hex()}"
        )
        key = file.get_key()
        local_identifier = file.get_local_identifier()

        skmt = b"\x00"
        if self.is_monitor:
            skmt = b"\x01"

        file_req = pb_base.FILE_REQUEST.MONITOR_REQ
        # work around. include WHO
        packed = (local_identifier, who)

        request = pb_base.FileServiceRequest(
            local_file_identifier=dill.dumps(packed),
            key=key,
            file_request=file_req,
            data=contents,
            process_id=self.process_id,
            is_monitor=skmt,
        )

        try:
            response = await self.stub.SendMonitorRequest(request, timeout=timeout)
        except:
            logger.warning("FILE - Error on stub send")
            await self.kp_channel.kill_update()
            return pb_base.DHTStatus.ERR
        await self.kp_channel.update()
        return response.status

    async def SendFileContents(
        self, file: HostedFile, contents: bytes, timeout=FILE_REQ_TIMEOUT
    ):
        logger.info(
            f"FILE - SendFileContents request: {file.get_key().hex()} - {file.local_identifier.hex()}"
        )
        key = file.get_key()
        local_identifier = file.get_local_identifier()

        skmt = b"\x00"
        if self.is_monitor:
            skmt = b"\x01"

        file_req = pb_base.FILE_REQUEST.CONTENTS
        request = pb_base.FileServiceRequest(
            local_file_identifier=local_identifier,
            key=key,
            file_request=file_req,
            data=contents,
            process_id=self.process_id,
            is_monitor=skmt,
        )
        try:
            response = await self.stub.SendFileContents(request, timeout=timeout)
        except:
            logger.warning("FILE - Error on stub send")
            await self.kp_channel.kill_update()
            return pb_base.DHTStatus.ERR

        await self.kp_channel.update()
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
        assert isinstance(key, bytes)
        assert isinstance(local_file_identifier, bytes)

        logger.info(
            f"FILE - OpenFile request recv: {key.hex()} - {local_file_identifier.hex()}"
        )

        if request.file_request != pb_base.FILE_REQUEST.OPEN:
            return pb_base.FileServiceResponse(status=pb_base.DHTStatus.ERR, data=b"")

        try:
            f, monitor_peer = await self.internal_callback.fetch_file(
                key,
                local_file_identifier,
                request.process_id,
                is_monitor=request.is_monitor == b"\x01",
            )
        except ValueError:
            is_monitor = request.is_monitor == b"\x01"
            logger.debug(f"FILE - OpenFile error 1 Monitor: {is_monitor}")
            return pb_base.FileServiceResponse(
                status=pb_base.DHTStatus.NOT_FOUND, data=b""
            )

        logger.debug(f"FILE - Received server file handler: {f.get_local_identifier()}")

        f.open()  # idempotent

        if request.is_monitor != b"\x01":
            tp = await self.internal_callback.get_peer_transport(monitor_peer)
            assert tp is not None
            while True:
                test = await self.internal_callback.keep_alive_manager.test(
                    tp, monitor_peer
                )
                if test:
                    break
                while True:
                    new_peer = self.internal_callback.file_manager.get_monitor(f)
                    if monitor_peer != new_peer:
                        break
                    await asyncio.sleep(0.02)  # wait for monitor to spawn
                    logger.debug("FILE - Waiting for monitor...")
                monitor_peer = new_peer
                tp = await self.internal_callback.get_peer_transport(monitor_peer)
                assert tp is not None
            fc = FileClient(tp, monitor_peer, request.process_id, is_monitor=True)
            await fc.OpenFile(f)

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
            f, monitor_peer = await self.internal_callback.fetch_file(
                key, local_file_identifier, is_monitor=request.is_monitor == b"\x01"
            )
        except:
            return pb_base.FileServiceResponse(
                status=pb_base.DHTStatus.NOT_FOUND, data=b""
            )

        length = int.from_bytes(request.data, "big", signed=True)
        # f.open()  # idempotent

        out = f.read(length)
        if request.is_monitor != b"\x01":
            tp = await self.internal_callback.get_peer_transport(monitor_peer)
            assert tp is not None
            while True:
                test = await self.internal_callback.keep_alive_manager.test(
                    tp, monitor_peer
                )
                if test:
                    break
                while True:
                    new_peer = self.internal_callback.file_manager.get_monitor(f)
                    if monitor_peer != new_peer:
                        break
                    await asyncio.sleep(0.02)  # wait for monitor to spawn
                    logger.debug("FILE - Waiting for monitor...")
                monitor_peer = new_peer
                tp = await self.internal_callback.get_peer_transport(monitor_peer)
                assert tp is not None
            fc = FileClient(tp, monitor_peer, request.process_id, is_monitor=True)
            await fc.ReadFile(f, length)

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
            f, monitor_peer = await self.internal_callback.fetch_file(
                key, local_file_identifier, is_monitor=request.is_monitor == b"\x01"
            )
        except ValueError:
            logger.debug(f"FILE - Writer check 2 error")
            return pb_base.FileServiceResponse(
                status=pb_base.DHTStatus.NOT_FOUND, data=b""
            )

        # f.open()  # idempotent
        f.write(request.data)

        if request.is_monitor != b"\x01":
            tp = await self.internal_callback.get_peer_transport(monitor_peer)
            assert tp is not None
            while True:
                test = await self.internal_callback.keep_alive_manager.test(
                    tp, monitor_peer
                )
                if test:
                    break
                while True:
                    new_peer = self.internal_callback.file_manager.get_monitor(f)
                    if monitor_peer != new_peer:
                        break
                    await asyncio.sleep(0.02)  # wait for monitor to spawn
                    logger.debug("FILE - Waiting for monitor...")
                monitor_peer = new_peer
                tp = await self.internal_callback.get_peer_transport(monitor_peer)
                assert tp is not None
            fc = FileClient(tp, monitor_peer, request.process_id, is_monitor=True)
            await fc.WriteFile(f, request.data)

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
            f, monitor_peer = await self.internal_callback.fetch_file(
                key, local_file_identifier, is_monitor=request.is_monitor == b"\x01"
            )
        except:
            return pb_base.FileServiceResponse(
                status=pb_base.DHTStatus.NOT_FOUND, data=b""
            )

        offset = int.from_bytes(request.data[:4], "big")
        whence = int.from_bytes(request.data[4:], "big")

        # f.open()  # idempotent
        f.seek(offset, whence)
        if request.is_monitor != b"\x01":
            tp = await self.internal_callback.get_peer_transport(monitor_peer)
            assert tp is not None
            while True:
                test = await self.internal_callback.keep_alive_manager.test(
                    tp, monitor_peer
                )
                if test:
                    break
                while True:
                    new_peer = self.internal_callback.file_manager.get_monitor(f)
                    if monitor_peer != new_peer:
                        break
                    await asyncio.sleep(0.02)  # wait for monitor to spawn
                    logger.debug("FILE - Waiting for monitor...")
                monitor_peer = new_peer
                tp = await self.internal_callback.get_peer_transport(monitor_peer)
                assert tp is not None
            fc = FileClient(tp, monitor_peer, request.process_id, is_monitor=True)
            await fc.SeekFile(f, offset, whence)

        return pb_base.FileServiceResponse(status=pb_base.DHTStatus.OK, data=b"")

    async def TellFile(
        self, request: pb_base.FileServiceRequest, context: grpc.aio.ServicerContext
    ) -> pb_base.FileServiceResponse:
        key = request.key
        local_file_identifier = request.local_file_identifier

        logger.info(
            f"FILE - TellFile request recv: {key.hex()} - {local_file_identifier.hex()}"
        )

        if request.is_monitor == b"\x01":
            logger.warning("FILE - TellFile on monitor object! Dropping.")

        if request.file_request != pb_base.FILE_REQUEST.TELL:
            return pb_base.FileServiceResponse(status=pb_base.DHTStatus.ERR, data=b"")

        try:
            f, monitor_peer = await self.internal_callback.fetch_file(
                key, local_file_identifier
            )
        except:
            return pb_base.FileServiceResponse(
                status=pb_base.DHTStatus.NOT_FOUND, data=b""
            )

        # f.open()  # idempotent
        position = f.tell()
        # if request.is_monitor != b"\x01": # doesn't do anything!
        #     tp = await self.internal_callback.get_peer_transport(monitor_peer)
        #     assert tp is not None
        #     fc = FileClient(tp, monitor_peer, request.process_id, is_monitor=True)
        #     await fc.TellFile(f)

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
            f, monitor_peer = await self.internal_callback.fetch_file(
                key, local_file_identifier, is_monitor=request.is_monitor == b"\x01"
            )
        except:
            return pb_base.FileServiceResponse(
                status=pb_base.DHTStatus.NOT_FOUND, data=b""
            )

        if request.is_monitor != b"\x01":
            tp = await self.internal_callback.get_peer_transport(monitor_peer)
            assert tp is not None
            while True:
                test = await self.internal_callback.keep_alive_manager.test(
                    tp, monitor_peer
                )
                if test:
                    break
                while True:
                    new_peer = self.internal_callback.file_manager.get_monitor(f)
                    if monitor_peer != new_peer:
                        break
                    await asyncio.sleep(0.02)  # wait for monitor to spawn
                    logger.debug("FILE - Waiting for monitor...")
                monitor_peer = new_peer
                tp = await self.internal_callback.get_peer_transport(monitor_peer)
                assert tp is not None
            fc = FileClient(tp, monitor_peer, request.process_id, is_monitor=True)
            await fc.CloseFile(f)

        self.internal_callback.close_file(
            key, local_file_identifier, is_monitor=request.is_monitor == b"\x01"
        )
        f.close()

        return pb_base.FileServiceResponse(status=pb_base.DHTStatus.OK, data=b"")

    # rpc SendMonitorRequest(FileServiceRequest) returns (FileServiceResponse) {}
    async def SendMonitorRequest(
        self, request: pb_base.FileServiceRequest, context: grpc.aio.ServicerContext
    ) -> pb_base.FileServiceResponse:
        key = request.key
        packed = request.local_file_identifier
        unpacked = dill.loads(packed)
        local_file_identifier = unpacked[0]
        who = unpacked[1]

        contents = request.data
        logger.info(
            f"FILE - SendMonitor request recv: {key.hex()} - {local_file_identifier.hex()} {contents}"
        )

        if request.file_request != pb_base.FILE_REQUEST.MONITOR_REQ:
            return pb_base.FileServiceResponse(status=pb_base.DHTStatus.ERR, data=b"")

        hf = HostedFile.from_key(key)
        hf.local_identifier = local_file_identifier

        await self.internal_callback.receive_file_monitor_request(hf, who, contents)
        return pb_base.FileServiceResponse(status=pb_base.DHTStatus.OK, data=b"")

    # // raw file transfer
    # rpc SendFileContents(FileServiceRequest) returns (FileServiceResponse) {}

    async def SendFileContents(
        self, request: pb_base.FileServiceRequest, context: grpc.aio.ServicerContext
    ) -> pb_base.FileServiceResponse:
        key = request.key
        local_file_identifier = request.local_file_identifier
        process_id = request.process_id

        logger.info(
            f"FILE - FileContentsRecv: {key.hex()} - {local_file_identifier.hex()}"
        )

        if request.file_request != pb_base.FILE_REQUEST.CONTENTS:
            return pb_base.FileServiceResponse(status=pb_base.DHTStatus.ERR, data=b"")

        try:
            f, monitor_peer = await self.internal_callback.fetch_file(
                key,
                local_file_identifier,
                process_id,
                direct_access=True,
                is_monitor=request.is_monitor == b"\x01",
            )
        except:
            return pb_base.FileServiceResponse(
                status=pb_base.DHTStatus.NOT_FOUND, data=b""
            )
        f.set_contents(request.data)
        return pb_base.FileServiceResponse(status=pb_base.DHTStatus.OK, data=b"")
