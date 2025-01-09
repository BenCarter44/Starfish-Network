# Class for code for the servicer
# Class for client

import asyncio
import logging
from typing import AsyncGenerator, Iterator

import grpc
from . import main_pb2 as pb_base
from . import main_pb2_grpc as pb

try:
    from ..core import star_components as star
    from ..core.star_components import StarAddress
except:
    from core import star_components as star
    from core.star_components import StarAddress

try:
    from src.plugboard import PlugBoard  # For typing purposes.
except:
    pass

import logging

logger = logging.getLogger(__name__)


def nice_print(bs):
    return " ".join(format(b, "08b") for b in bs)


class DHTClient:
    # Sends requests to network.
    def __init__(self, channel: grpc.aio.Channel, addr_to: bytes, addr_me: bytes):
        self.stub = pb.DHTServiceStub(channel)
        self.peer_id = addr_to
        self.peer_me = addr_me

    async def FetchItem(
        self, key: bytes, select: pb_base.DHTSelect, nodes_visited: list[bytes] = []
    ) -> tuple[bytes, pb_base.DHTStatus, pb_base.DHTSelect]:

        logger.debug("Create FetchItem request")
        logger.debug(f"[{key.hex()}]")
        peer_id = self.peer_id
        request = pb_base.DHT_Fetch_Request(
            key=key, select=select, query_chain=nodes_visited
        )
        response = await self.stub.FetchItem(request)
        return response.value, response.status, response.select

    async def StoreItem(
        self,
        key: bytes,
        value: bytes,
        select: pb_base.DHTSelect,
        nodes_visited: list[bytes] = [],
    ) -> tuple[pb_base.DHTStatus, bytes]:
        peer_id = self.peer_id

        logger.debug("Create StoreItem request")
        val = value.hex()
        if len(val) > 32:
            val = val[0:32] + "..."
        logger.debug(f'[{key.hex()}] = "{val}"')
        request = pb_base.DHT_Store_Request(
            key=key,
            value=value,
            select=select,
            query_chain=nodes_visited,
            who=self.peer_id,
        )
        request.query_chain.append(peer_id)
        for x in request.query_chain:
            logger.debug(f"Visited: {x.hex()}")
        response = await self.stub.StoreItem(request)
        # try:
        #     response_stream =
        #     async for r in response_stream:
        #         print(r)
        #         response = r
        # except Exception as e:
        #     logger.error(e)
        logger.debug("Received StoreItem request response")
        return response.status, response.who

    async def delete(self, key: bytes, select: pb_base.DHTSelect):
        logger.debug("Create Delete request")
        resp = await self.stub.DeleteItem(
            pb_base.DHT_Delete_Request(key=key, select=select)
        )
        return resp.status

    async def send_deletion_notice(self, key: bytes, select: pb_base.DHTSelect):
        logger.debug("Create Delete notice request")
        resp = await self.stub.DeletedNotice(
            pb_base.DHT_Delete_Notice_Request(key=key, select=select)
        )
        return resp.status

    async def update(self, key: bytes, value: bytes, select: pb_base.DHTSelect):
        logger.debug("Create update request")
        resp = await self.stub.UpdateItem(
            pb_base.DHT_Update_Request(key=key, value=value, select=select)
        )
        return resp.status

    async def send_update_notice(
        self, key: bytes, value: bytes, select: pb_base.DHTSelect
    ):
        logger.debug("Create update notice request")
        resp = await self.stub.UpdatedNotice(
            pb_base.DHT_Update_Notice_Request(key=key, value=value, select=select)
        )
        return resp.status

    async def register_notices(self, key: bytes, select: pb_base.DHTSelect):
        logger.debug(
            f"Create register notice request for key [{key.hex()}] going to {self.peer_id.hex()}"
        )
        resp = await self.stub.RegisterNotice(
            pb_base.DHT_Register_Notices_Request(
                key=key, select=select, who=self.peer_me
            )
        )
        return resp.status


class DHTService(pb.DHTServiceServicer):
    def __init__(self, internal_callback: "PlugBoard", my_addr):
        self.internal_callback = internal_callback
        self.addr = my_addr

    async def FetchItem(
        self,
        request: pb_base.DHT_Fetch_Request,
        context: grpc.aio.ServicerContext,
    ) -> pb_base.DHT_Fetch_Response:

        nodes_visited: list[bytes] = request.query_chain  # type: ignore
        peers_update = set(nodes_visited)
        await self.internal_callback.update_peers_seen(peers_update)  # internal.
        nodes_visited.append(self.addr)
        logger.debug("Got FetchItem request")
        logger.debug(f"[{request.key.hex()}]")
        for x in nodes_visited:
            logger.debug(f"Visited: {x.hex()}")
        if request.select == pb_base.DHTSelect.PEER_ID:
            peer_id = nice_print(request.key)
            # peer_id = request.key.decode("utf-8")
            logger.debug(f"Decoded PEER: [{request.key.hex()}]")
        elif request.select == pb_base.DHTSelect.TASK_ID:
            task_addr = nice_print(request.key)  # task ID in bytes

        data, status, neighbors = self.internal_callback.dht_get_plain(
            request.key, request.select
        )
        if (
            status == pb_base.DHTStatus.OWNED or status == pb_base.DHTStatus.FOUND
        ):  # I own it or in cache.
            logger.debug(f"I {self.addr.hex()} have {request.key.hex()}")
            return pb_base.DHT_Fetch_Response(
                key=request.key,
                value=data,
                query_chain=nodes_visited,
                status=pb_base.DHTStatus.FOUND,
                select=request.select,
            )
        # Not found. Query peers.
        logger.debug(f"Not found, query neighbors.")
        for addr in neighbors:
            if addr in nodes_visited:
                continue

            logger.debug(f"Neighbor: {addr.hex()}")

            # internal_callback. Get peer
            transport: StarAddress | None = (
                await self.internal_callback.get_peer_transport(addr)
            )
            if transport is None:
                logger.info(f"Transport for {addr.hex()} not found!")
                continue

            channel = transport.get_channel()
            dhtClient = DHTClient(channel, addr, self.addr)
            response, status, select = await dhtClient.FetchItem(
                request.key, request.select, nodes_visited=nodes_visited
            )
            # await channel.close()
            if status == pb_base.DHTStatus.NOT_FOUND:
                continue
            await self.internal_callback.dht_cache_store(
                request.key, response, request.select, addr
            )
            return pb_base.DHT_Fetch_Response(
                key=request.key,
                value=response,
                query_chain=nodes_visited,
                status=pb_base.DHTStatus.FOUND,
                select=request.select,
            )

        logger.info(f"No Neighbors! Not FOUND for fetch! Key: {request.key.hex()}")
        return pb_base.DHT_Fetch_Response(
            key=request.key,
            value=data,
            query_chain=nodes_visited,
            status=pb_base.DHTStatus.NOT_FOUND,
            select=request.select,
        )

    async def StoreItem(
        self,
        request: pb_base.DHT_Store_Request,
        context: grpc.aio.ServicerContext,
    ) -> pb_base.DHT_Store_Response:
        logger.debug("Got StoreItem request")
        val = request.value.hex()
        if len(val) > 32:
            val = val[0:32] + "..."
        logger.debug(f'[{request.key.hex()}] = "{val}"')
        if request.select == pb_base.DHTSelect.PEER_ID:
            # peer_id = nice_print(request.key)
            # peer_id = request.key.decode("utf-8")
            val = StarAddress.from_bytes(request.value)
            logger.debug(
                f"Decoded PEER: [{request.key.hex()}] = {val.get_string_channel()}"
            )
        elif request.select == pb_base.DHTSelect.TASK_ID:
            task_addr = nice_print(request.key)  # task ID in bytes

        nodes_visited: list[bytes] = request.query_chain  # type: ignore
        for x in nodes_visited:
            logger.debug(f"Visited: {x.hex()}")
        peers_update = set(nodes_visited)
        await self.internal_callback.update_peers_seen(peers_update)  # internal.

        if len(nodes_visited) > 0:
            monitor = nodes_visited[-1]
        else:
            monitor = request.who

        data, status, neighbors = await self.internal_callback.dht_set_plain(
            request.key, request.value, request.select, monitor
        )
        nodes_visited.append(self.addr)

        if status == pb_base.DHTStatus.OWNED:  # I own it.
            logger.debug(f"I {self.addr.hex()} now own record {request.key.hex()}")
            return pb_base.DHT_Store_Response(
                key=request.key,
                query_chain=nodes_visited,
                status=pb_base.DHTStatus.OWNED,
                select=request.select,
                who=self.addr,
            )

        my_nice = nice_print(self.addr)
        logger.debug(f"Push to neighbors!")
        # Neighbor has to own it.
        send_tos = []
        for neighbor in neighbors:
            if neighbor not in nodes_visited:
                send_tos.append(neighbor)
                logger.debug(f"Neighbor: {neighbor.hex()}")

        for addr in send_tos:
            # send to neighbor.
            logger.debug(f"Send out Neighbor: {neighbor.hex()}")
            # internal_callback. Get peer
            transport = await self.internal_callback.get_peer_transport(addr)
            if transport is None:
                logger.info(f"Transport for {addr.hex()} not found!")
                continue

            channel = transport.get_channel()
            dhtClient = DHTClient(channel, addr, self.addr)
            response, who = await dhtClient.StoreItem(
                request.key, request.value, request.select, nodes_visited=nodes_visited
            )
            return pb_base.DHT_Store_Response(
                key=request.key,
                query_chain=nodes_visited,
                status=pb_base.DHTStatus.FOUND,
                select=request.select,
                who=who,
            )

        logger.info(f"No Neighbors! Not FOUND for store! Key: {request.key.hex()}")
        return pb_base.DHT_Store_Response(
            key=request.key,
            query_chain=nodes_visited,
            status=pb_base.DHTStatus.NOT_FOUND,
            select=request.select,
            who=self.addr,
        )

    async def DeleteItem(
        self,
        request: pb_base.DHT_Delete_Request,
        context: grpc.aio.ServicerContext,
    ) -> pb_base.DHT_Delete_Response:
        logger.debug("Delete Item Request Server")
        resp = await self.internal_callback.dht_delete_plain(
            request.key, request.select
        )
        return pb_base.DHT_Delete_Response(status=resp)

    async def DeletedNotice(
        self,
        request: pb_base.DHT_Delete_Notice_Request,
        context: grpc.aio.ServicerContext,
    ) -> pb_base.DHT_Delete_Notice_Response:
        logger.debug("Deleted Notice Request Server")
        resp = await self.internal_callback.dht_delete_notice_plain(
            request.key, request.select
        )
        return pb_base.DHT_Delete_Notice_Response(status=resp)

    async def UpdateItem(
        self,
        request: pb_base.DHT_Update_Request,
        context: grpc.aio.ServicerContext,
    ) -> pb_base.DHT_Update_Response:
        logger.debug("Update Item Request Server")
        resp = await self.internal_callback.dht_update_plain(
            request.key, request.select
        )
        return pb_base.DHT_Update_Response(status=resp)

    async def UpdatedNotice(
        self,
        request: pb_base.DHT_Update_Notice_Request,
        context: grpc.aio.ServicerContext,
    ) -> pb_base.DHT_Update_Notice_Response:
        logger.debug("Updated Notice Request Server")
        resp = await self.internal_callback.dht_update_notice_plain(
            request.key, request.select
        )
        return pb_base.DHT_Update_Notice_Response(status=resp)

    async def RegisterNotice(
        self,
        request: pb_base.DHT_Register_Notices_Request,
        context: grpc.aio.ServicerContext,
    ) -> pb_base.DHT_Register_Notices_Response:
        logger.debug("Register Notice Request Server")
        self.internal_callback.cache_subscriptions[request.select][request.key].append(
            request.who
        )

        return pb_base.DHT_Register_Notices_Response(status=pb_base.DHTStatus.OK)
