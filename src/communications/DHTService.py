# Class for code for the servicer
# Class for client

import asyncio
import logging
from typing import AsyncGenerator, Iterator

import grpc

from src.KeepAlive import KeepAlive_Channel
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
    def __init__(
        self, transport: StarAddress, addr_to: bytes, addr_me: bytes, keep_alive
    ):
        channel = keep_alive.get_channel(transport.get_string_channel())
        self.kp_channel = keep_alive.get_kp_channel(transport, addr_to)
        self.stub = pb.DHTServiceStub(channel)
        self.peer_id = addr_to
        self.peer_me = addr_me

    async def FetchItem(
        self,
        key: bytes,
        select: pb_base.DHTSelect,
        nodes_visited: list[bytes] = [],
        timeout=0.2,
    ) -> tuple[bytes, pb_base.DHTStatus, pb_base.DHTSelect]:

        logger.debug(f"DHT - Create FetchItem request")
        logger.debug(f"DHT - [{key.hex()}]")
        peer_id = self.peer_id
        request = pb_base.DHT_Fetch_Request(
            key=key, select=select, query_chain=nodes_visited
        )

        try:
            response = await self.stub.FetchItem(request, timeout=timeout)
        except Exception as e:
            logger.warning(f"FetchItem error {e}")
            await self.kp_channel.kill_update()
            return b"", pb_base.DHTStatus.ERR, pb_base.DHTSelect.BLANK

        self.kp_channel.update()
        return response.value, response.status, response.select

    async def StoreItem(
        self,
        key: bytes,
        value: bytes,
        select: pb_base.DHTSelect,
        nodes_visited: list[bytes] = [],
        timeout=0.2,
    ) -> tuple[pb_base.DHTStatus, bytes]:
        peer_id = self.peer_id

        logger.debug(f"DHT - Create StoreItem request. send to {self.peer_id.hex()}")
        val = value.hex()
        if len(val) > 32:
            val = val[0:32] + "..."
        logger.debug(f'DHT - [{key.hex()}] = "{val}"')
        request = pb_base.DHT_Store_Request(
            key=key,
            value=value,
            select=select,
            query_chain=nodes_visited,
            who=self.peer_id,
        )
        # request.query_chain.append(peer_id)
        # for x in request.query_chain:
        #     logger.debug(f"DHT - Visited: {x.hex()}")

        try:
            response = await self.stub.StoreItem(request, timeout=timeout)
        except Exception as e:
            logger.warning(f"DHT - StoreItem error {e}")
            await self.kp_channel.kill_update()
            return pb_base.DHTStatus.ERR, b""

        self.kp_channel.update()
        # try:
        #     response_stream =
        #     async for r in response_stream:
        #         print(r)
        #         response = r
        # except Exception as e:
        #     logger.error(e)
        logger.debug(f"DHT - Received StoreItem request response")
        return response.status, response.who

    async def delete(self, key: bytes, select: pb_base.DHTSelect, timeout=0.2):
        logger.warning(f"DHT - Create Delete request")

        try:
            resp = await self.stub.DeleteItem(
                pb_base.DHT_Delete_Request(key=key, select=select, who=self.peer_me),
                timeout=timeout,
            )
        except Exception as e:
            logger.debug(f"DHT - Delete error")
            await self.kp_channel.kill_update()
            return pb_base.DHTStatus.ERR

        self.kp_channel.update()
        return resp.status

    async def send_deletion_notice(
        self, key: bytes, select: pb_base.DHTSelect, timeout=0.2
    ):
        logger.debug(f"DHT - Create Delete notice request")

        logger.debug(f"DHT - {key}")
        logger.debug(f"DHT - {select}")
        logger.debug(f"DHT - {self.peer_me}")
        resp = await self.stub.DeletedNotice(
            pb_base.DHT_Delete_Notice_Request(key=key, select=select, who=self.peer_me),
            timeout=timeout,
        )

        # try:
        #     resp = await self.stub.DeletedNotice(
        #         pb_base.DHT_Delete_Notice_Request(
        #             key=key, select=select, who=self.peer_me
        #         ),
        #         timeout=timeout,
        #     )
        # except Exception as e:
        #     logger.warning(f"Deletion notice error {e}")
        #     await self.kp_channel.kill_update()
        #     return pb_base.DHTStatus.ERR

        self.kp_channel.update()
        return resp.status

    async def update(
        self, key: bytes, value: bytes, select: pb_base.DHTSelect, timeout=0.2
    ):
        logger.debug(f"DHT - Create update request")

        try:
            resp = await self.stub.UpdateItem(
                pb_base.DHT_Update_Request(
                    key=key, value=value, select=select, who=self.peer_me
                ),
                timeout=timeout,
            )
        except Exception as e:
            logger.debug(f"DHT - Deletion notice error")
            await self.kp_channel.kill_update()
            return pb_base.DHTStatus.ERR

        self.kp_channel.update()
        return resp.status

    async def send_update_notice(
        self, key: bytes, value: bytes, select: pb_base.DHTSelect, timeout=0.2
    ):
        logger.debug(f"DHT - Create update notice request")

        try:
            resp = await self.stub.UpdatedNotice(
                pb_base.DHT_Update_Notice_Request(
                    key=key, value=value, select=select, who=self.peer_me
                ),
                timeout=timeout,
            )
        except Exception as e:
            logger.debug(f"DHT - Create notice error")
            await self.kp_channel.kill_update()
            return pb_base.DHTStatus.ERR

        self.kp_channel.update()
        return resp.status

    async def register_notices(
        self, key: bytes, select: pb_base.DHTSelect, timeout=0.2
    ):

        if self.peer_id == self.peer_me:
            logger.debug(
                f"DHT - Drop Create register notice request for key [{key.hex()}] going to {self.peer_id.hex()} AS IS SAME"
            )
            return pb_base.DHTStatus.FOUND

        logger.debug(
            f"DHT - Create register notice request for key [{key.hex()}] going to {self.peer_id.hex()}"
        )

        try:
            resp = await self.stub.RegisterNotice(
                pb_base.DHT_Register_Notices_Request(
                    key=key, select=select, who=self.peer_me
                ),
                timeout=timeout,
            )
        except Exception as e:
            logger.debug(f"DHT - Register notice error")
            await self.kp_channel.kill_update()
            return pb_base.DHTStatus.ERR

        logger.debug(f"DHT - Done. Create Register notice request")
        self.kp_channel.update()
        return resp.status


class DHTService(pb.DHTServiceServicer):
    def __init__(self, internal_callback: "PlugBoard", my_addr, keep_alive):
        self.internal_callback = internal_callback
        self.addr = my_addr
        self.keep_alive = keep_alive

    async def FetchItem(
        self,
        request: pb_base.DHT_Fetch_Request,
        context: grpc.aio.ServicerContext,
    ) -> pb_base.DHT_Fetch_Response:

        nodes_visited: list[bytes] = request.query_chain  # type: ignore
        peers_update = set(nodes_visited)
        await self.internal_callback.update_peers_seen(peers_update)  # internal.

        # peer_address = context.peer()
        # await self.keep_alive.receive_ping(peer_address)

        logger.debug(f"DHT - Got FetchItem request")
        logger.debug(f"DHT - [{request.key.hex()}]")
        for x in nodes_visited:
            logger.debug(f"DHT - Visited: {x.hex()}")
        nodes_visited.append(self.addr)

        # if request.select == pb_base.DHTSelect.PEER_ID:
        #     peer_id = nice_print(request.key)
        #     # peer_id = request.key.decode("utf-8")
        #     logger.debug(f"DHT - Decoded PEER: [{request.key.hex()}]")
        # elif request.select == pb_base.DHTSelect.TASK_ID:
        #     task_addr = nice_print(request.key)  # task ID in bytes

        data, status, neighbors = self.internal_callback.dht_get_plain(
            request.key, request.select
        )
        if (
            status == pb_base.DHTStatus.OWNED or status == pb_base.DHTStatus.FOUND
        ):  # I own it or in cache.
            logger.debug(f"DHT - I {self.addr.hex()} have {request.key.hex()}")
            return pb_base.DHT_Fetch_Response(
                key=request.key,
                value=data,
                query_chain=nodes_visited,
                status=pb_base.DHTStatus.FOUND,
                select=request.select,
            )
        # Not found. Query peers.
        logger.debug(f"DHT - Not found, query neighbors.")
        for addr in neighbors:
            if addr in nodes_visited:
                continue

            logger.debug(f"DHT - Neighbor: {addr.hex()}")

            # internal_callback. Get peer
            transport: StarAddress | None = (
                await self.internal_callback.get_peer_transport(addr)
            )
            if transport is None:
                logger.info(f"DHT - Transport for {addr.hex()} not found!")
                continue

            dhtClient = DHTClient(transport, addr, self.addr, self.keep_alive)
            response, status, select = await dhtClient.FetchItem(
                request.key, request.select, nodes_visited=nodes_visited
            )
            # await channel.close()
            if status == pb_base.DHTStatus.NOT_FOUND or status == pb_base.DHTStatus.ERR:
                continue
            logger.debug(f"DHT - DHT Cache store pre")
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

        logger.info(
            f"DHT - No Neighbors! Not FOUND for fetch! Key: {request.key.hex()}"
        )
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
        logger.debug(f"DHT - Got StoreItem request")

        # peer_address = context.peer()
        # await self.keep_alive.receive_ping(peer_address)

        val = request.value.hex()
        if len(val) > 32:
            val = val[0:32] + "..."
        if request.select == pb_base.DHTSelect.PEER_ID:
            # peer_id = nice_print(request.key)
            # peer_id = request.key.decode("utf-8")
            val = StarAddress.from_bytes(request.value)
            logger.debug(
                f"PEER: [{request.key.hex()}] = {val.get_string_channel()}"  # type: ignore
            )
        elif request.select == pb_base.DHTSelect.TASK_ID:
            logger.debug(f'DHT - T: [{request.key.hex()}] = "{val}"')
        #     task_addr = nice_print(request.key)  # task ID in bytes

        nodes_visited: list[bytes] = request.query_chain  # type: ignore
        if request.select == pb_base.DHTSelect.TASK_ID:
            for x in nodes_visited:
                logger.debug(f"DHT - Visited: {x.hex()}")
        peers_update = set(nodes_visited)
        await self.internal_callback.update_peers_seen(peers_update)  # internal.

        # Initial query has no callback!
        # Need to test: ignore all addresses that are in ignore list.
        data, status, neighbors = await self.internal_callback.dht_set_plain(
            request.key, request.value, request.select, request.who, ignore=peers_update
        )
        nodes_visited.append(self.addr)

        if status == pb_base.DHTStatus.OWNED:  # I own it.
            logger.debug(
                f"DHT - I {self.addr.hex()} now own record {request.key.hex()}"
            )
            return pb_base.DHT_Store_Response(
                key=request.key,
                query_chain=nodes_visited,
                status=pb_base.DHTStatus.OWNED,
                select=request.select,
                who=self.addr,
            )

        my_nice = nice_print(self.addr)
        logger.debug(f"DHT - Push to neighbors!")
        # Neighbor has to own it.
        send_tos = []
        for neighbor in neighbors:
            if neighbor not in nodes_visited:
                send_tos.append(neighbor)
                # logger.debug(f"DHT - Neighbor: {neighbor.hex()}")

        for addr in send_tos:
            # send to neighbor.
            logger.debug(f"DHT - Send out Neighbor: {neighbor.hex()}")
            # internal_callback. Get peer
            transport = await self.internal_callback.get_peer_transport(addr)
            if transport is None:
                logger.info(f"DHT - Transport for {addr.hex()} not found!")
                continue

            logger.debug(f"DHT - {transport.get_string_channel()}")
            dhtClient = DHTClient(transport, addr, self.addr, self.keep_alive)
            response, who = await dhtClient.StoreItem(
                request.key, request.value, request.select, nodes_visited=nodes_visited
            )

            # add who
            await self.internal_callback.dht_set_cache_notices(
                request.key, request.value, request.select, addr
            )

            return pb_base.DHT_Store_Response(
                key=request.key,
                query_chain=nodes_visited,
                status=pb_base.DHTStatus.FOUND,
                select=request.select,
                who=who,
            )

        logger.info(
            f"DHT - No Neighbors! Not FOUND for store! Key: {request.key.hex()}"
        )
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
        logger.debug(f"DHT - Recv Delete Item Request Server")

        # peer_address = context.peer()
        # await self.keep_alive.receive_ping(peer_address)

        resp = await self.internal_callback.dht_delete_plain(
            request.key, request.select
        )
        return pb_base.DHT_Delete_Response(status=resp)

    async def DeletedNotice(
        self,
        request: pb_base.DHT_Delete_Notice_Request,
        context: grpc.aio.ServicerContext,
    ) -> pb_base.DHT_Delete_Notice_Response:
        logger.debug(f"DHT - Recv Deleted Notice Request Server")

        # peer_address = context.peer()
        # await self.keep_alive.receive_ping(peer_address)

        resp = await self.internal_callback.dht_delete_notice_plain(
            request.key, request.select
        )
        return pb_base.DHT_Delete_Notice_Response(status=resp)

    async def UpdateItem(
        self,
        request: pb_base.DHT_Update_Request,
        context: grpc.aio.ServicerContext,
    ) -> pb_base.DHT_Update_Response:
        logger.debug(f"DHT - Recv Update Item Request Server")

        # peer_address = context.peer()
        # await self.keep_alive.receive_ping(peer_address)

        resp = await self.internal_callback.dht_update_plain(
            request.key, request.select
        )
        return pb_base.DHT_Update_Response(status=resp)

    async def UpdatedNotice(
        self,
        request: pb_base.DHT_Update_Notice_Request,
        context: grpc.aio.ServicerContext,
    ) -> pb_base.DHT_Update_Notice_Response:
        logger.debug(f"DHT - Recv Updated Notice Request Server")

        # peer_address = context.peer()
        # await self.keep_alive.receive_ping(peer_address)

        resp = await self.internal_callback.dht_update_notice_plain(
            request.key, request.select
        )
        return pb_base.DHT_Update_Notice_Response(status=resp)

    async def RegisterNotice(
        self,
        request: pb_base.DHT_Register_Notices_Request,
        context: grpc.aio.ServicerContext,
    ) -> pb_base.DHT_Register_Notices_Response:
        logger.debug(
            f"DHT - Recv Register Notice Request Server from {request.who.hex()} for [{request.key.hex()}]"
        )

        # peer_address = context.peer()
        # await self.keep_alive.receive_ping(peer_address)

        self.internal_callback.cache_subscriptions_serve[request.select][
            request.key
        ].add(request.who)

        self.internal_callback.print_cache_subscriptions_serve()

        return pb_base.DHT_Register_Notices_Response(status=pb_base.DHTStatus.OK)
