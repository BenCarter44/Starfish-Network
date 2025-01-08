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
    def __init__(self, channel: grpc.Channel, addr_to: bytes):
        self.stub = pb.DHTServiceStub(channel)
        self.peer_id = addr_to

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
            key=key, value=value, select=select, query_chain=nodes_visited
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


class DHTService(pb.DHTServiceServicer):
    def __init__(self, internal_callback: "PlugBoard", my_addr):
        self.internal_callback = internal_callback
        self.addr = my_addr

    async def FetchItem(
        self,
        request: pb_base.DHT_Fetch_Request,
        context: grpc.aio.ServicerContext,
    ) -> pb_base.DHT_Fetch_Response:

        nodes_visited = request.query_chain
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
            transport: StarAddress = await self.internal_callback.get_peer_transport(
                addr
            )
            if transport is None:
                logger.info(f"Transport for {addr.hex()} not found!")
                continue

            channel = transport.get_channel()
            dhtClient = DHTClient(channel, self.addr)
            response, status, select = await dhtClient.FetchItem(
                request.key, request.select, nodes_visited=nodes_visited
            )
            await channel.close()
            if status == pb_base.DHTStatus.NOT_FOUND:
                continue
            self.internal_callback.dht_cache_store(
                request.key, response, request.select
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

        nodes_visited = request.query_chain
        for x in nodes_visited:
            logger.debug(f"Visited: {x.hex()}")
        peers_update = set(nodes_visited)
        await self.internal_callback.update_peers_seen(peers_update)  # internal.
        nodes_visited.append(self.addr)

        data, status, neighbors = await self.internal_callback.dht_set_plain(
            request.key, request.value, request.select
        )

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
            dhtClient = DHTClient(channel, self.addr)
            response = await dhtClient.StoreItem(
                request.key, request.value, request.select, nodes_visited=nodes_visited
            )
            await channel.close()
            return pb_base.DHT_Store_Response(
                key=request.key,
                query_chain=nodes_visited,
                status=pb_base.DHTStatus.FOUND,
                select=request.select,
                who=response.who,
            )

        logger.info(f"No Neighbors! Not FOUND for store! Key: {request.key.hex()}")
        return pb_base.DHT_Store_Response(
            key=request.key,
            query_chain=nodes_visited,
            status=pb_base.DHTStatus.NOT_FOUND,
            select=request.select,
            who=self.addr,
        )
