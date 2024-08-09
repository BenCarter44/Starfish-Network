import threading
import time
from typing import Any, Optional

import zmq
from src.SharedKV import KeyValueCommunications
from src.node import Owned_Node, Node
from src.ttl import DataTTL
from src.utils import zpipe
from src.GraphEngine import display_graph
import io

# neighbors = {101:[102], 102:[103,104], 104:[105], 105:[103], 103:[101]}

DEFAULT_TEMP_TIME = 3


def main_worker(identity, control: zmq.Socket):
    """A container for one peer. Starts the keyvalue engine for the peer

    Args:
        identity (_type_): _description_
        control (zmq.Socket): _description_
    """
    my_endpoint = f"tcp://127.0.0.1:8{identity}"
    my_node = Owned_Node(endpoint=my_endpoint, identity=identity)

    poller = zmq.Poller()
    poller.register(control, zmq.POLLIN)
    while True:
        socket_recv = dict(poller.poll(1000))
        if control in socket_recv:
            msg = control.recv_multipart()
            if msg[0] == b"Connect":
                requested_peer = msg[1].decode("utf-8")
                if requested_peer == my_endpoint:
                    # error!
                    my_node.debug_printf("Test : Error - Can't connect to itself")
                    continue

                exists = False
                connect_peer: Optional[Node] = None
                global_peers = my_node.get_global_node_network_by_endpoint()
                for peer in global_peers:
                    if requested_peer == peer.endpoint.get_value_or_null():  # type: ignore
                        exists = True
                        connect_peer = peer
                        break

                if not (exists):
                    my_node.debug_printf(
                        f"Wanting to connect to {requested_peer} but it currently does not exist in global registry. Doing anyway"
                    )
                    connect_peer = Node(
                        endpoint=DataTTL(
                            requested_peer, time.time() + DEFAULT_TEMP_TIME
                        )
                    )

                my_node.connect_to_node(connect_peer)  # type: ignore
                my_node.debug_printf(
                    f"Test : Connected to {connect_peer.endpoint.get_raw_val()}"  # type: ignore
                )
            if msg[0] == b"ls":
                peers = my_node.get_inbound_connected_nodes()
                for peer in peers:
                    my_node.debug_printf(
                        f"Inbound      | {peer.endpoint.get_value_or_null()} | {peer.identity.get_value_or_null()}"
                    )
                peers = my_node.get_outbound_connected_nodes()
                for peer in peers:
                    my_node.debug_printf(
                        f"Outbound     | {peer.endpoint.get_value_or_null()} | {peer.identity.get_value_or_null()}"
                    )
                peers = my_node.get_global_node_network_by_endpoint()
                for peer in peers:
                    my_node.debug_printf(
                        f"Global Endpt | {peer.endpoint.get_value_or_null()} | {peer.identity.get_value_or_null()}"
                    )
                peers = my_node.get_global_node_network_by_identity()
                for peer in peers:
                    my_node.debug_printf(
                        f"Global ID    | {peer.endpoint.get_value_or_null()} | {peer.identity.get_value_or_null()}"
                    )
                my_node.debug_printf("===")
                streams = my_node.receiving_get_streams()
                for stream in streams:
                    i = my_node.receiving_read(stream)
                    if isinstance(i, io.BytesIO):
                        my_node.debug_printf(f"{stream}    | {i.getvalue()!r}")
                    else:
                        i.seek(0, 0)
                        with open(f"/tmp/{stream}.txt", "wb") as f:
                            f.write(i.read())
                        my_node.debug_printf(f"{stream}    | '/tmp/{stream}.txt'")

                net_g = my_node.get_network_graph()
                display_graph(net_g)

            if msg[0] == b"Disconnect":
                requested_peer = msg[1].decode("utf-8")
                if requested_peer == my_endpoint:
                    # error!
                    my_node.debug_printf("Test : Error - Can't disconnect to itself")
                    continue

                exists = False
                disconnect_peer: Optional[Node] = None
                global_peers = my_node.get_global_node_network_by_endpoint()
                for peer in global_peers:
                    if requested_peer == peer.endpoint.get_value_or_null():  # type: ignore
                        exists = True
                        disconnect_peer = peer
                        break

                if not (exists):
                    my_node.debug_printf(
                        f"Disconnect from {requested_peer} but it currently does not exist in global registry. Doing anyway. ERROR!"
                    )
                    raise NotImplementedError
                    disconnect_peer = Node(
                        endpoint=DataTTL(
                            requested_peer, time.time() + DEFAULT_TEMP_TIME
                        )
                    )

                my_node.disconnect_from_node(disconnect_peer)  # type: ignore
                my_node.debug_printf(f"Test : Disconnected from {requested_peer}")

            if msg[0] == b"SendData-C":
                my_node.debug_printf(f"Not doing anything anymore for send command sim")

            if msg[0] == b"SendData-D":
                requested_peer = int(msg[1].decode("utf-8"))  # type: ignore
                data = msg[2].decode("utf-8")

                exists = False
                send_peer: Optional[Node] = None
                global_peers = my_node.get_global_node_network_by_identity()
                for peer in global_peers:
                    if requested_peer == peer.identity.get_value_or_null():  # type: ignore
                        exists = True
                        send_peer = peer
                        break

                if not (exists):
                    my_node.debug_printf(
                        f"Sending to peer {requested_peer} but it currently does not exist in global registry. Doing anyway. ERROR!"
                    )
                    raise NotImplementedError

                try:
                    my_node.send_data_to(send_peer, io.BytesIO(data.encode()), find_routes=4)  # type: ignore
                except ValueError as e:
                    my_node.debug_printf(
                        f"Test : Sent data from {identity} to {requested_peer} ERROR! {e}"
                    )

            if msg[0] == b"SendData-F":
                requested_peer = int(msg[1].decode("utf-8"))  # type: ignore
                data = msg[2].decode("utf-8")

                f_data = open(data, "rb")

                exists = False
                send_peer: Optional[Node] = None
                global_peers = my_node.get_global_node_network_by_identity()
                for peer in global_peers:
                    if requested_peer == peer.identity.get_value_or_null():  # type: ignore
                        exists = True
                        send_peer = peer
                        break

                if not (exists):
                    my_node.debug_printf(
                        f"Sending to peer {requested_peer} but it currently does not exist in global registry. Doing anyway. ERROR!"
                    )
                    raise NotImplementedError

                try:
                    my_node.send_data_to(send_peer, f_data, find_routes=4)  # type: ignore
                except ValueError as e:
                    my_node.debug_printf(
                        f"Test : Sent data from {identity} to {requested_peer} ERROR! {e}"
                    )
                f_data.close()

            if msg[0] == b"set":
                key = msg[1].decode("utf-8")
                val = msg[2].decode("utf-8")
                my_node.debug_printf(f"Test : Set key")
                my_node.set(key, val, ttl=time.time() + 60)

            if msg[0] == b"STOP":
                break
            if msg[0] == b"print":
                my_node.debug_dump_kv()

    my_node.stop_communications()


ctx = zmq.Context()

peers: dict[int, Any] = {}
for id_num in range(101, 110 + 1):

    mine, theirs = zpipe(ctx)
    peers[id_num] = {"soc": mine, "node": None}
    th = threading.Thread(None, main_worker, args=(id_num, theirs))
    th.start()
    peers[id_num]["th"] = th

while True:
    print("What would you like to do? ")
    c = ""
    try:
        c = input("/? \n")
    except KeyboardInterrupt:
        c = "exit"
    if c == "exit":
        for peer in peers:
            peers[peer]["soc"].send_multipart([b"STOP"])
            peers[peer]["th"].join()
            print(f"Quit {peer}")
        break

    if c.find("disconnect") != -1:
        # first is node origin
        # second is the node to connect to
        c_tokens: list[int] = c.split(" ")  # type: ignore

        # Will be converted to int right below
        try:
            for x in range(1, len(c_tokens)):
                c_tokens[x] = int(c_tokens[x])
            if len(c_tokens) < 3:
                raise ValueError
        except:
            print("Bad command")
            continue

        if c_tokens[1] in peers:
            inp = c_tokens[2]
            endpoint = f"tcp://127.0.0.1:8{inp}"

            peers[c_tokens[1]]["soc"].send_multipart(
                [b"Disconnect", endpoint.encode("utf-8")]
            )
            # time.sleep(1)
            # peers[c_tokens[2]]["soc"].send_multipart([b'Disconnect',int.to_bytes(int(c_tokens[1]),1,'big')])
        else:
            print("Unknown peer")
        continue

    if c.find("ls") != -1:
        # first is node origin
        # second is the node to connect to
        c_tokens: list[int] = c.split(" ")  # type: ignore

        # Will be converted to int right below
        try:
            c_tokens[1] = int(c_tokens[1])
        except:
            print("Bad command")
            continue

        if c_tokens[1] in peers:

            peers[c_tokens[1]]["soc"].send_multipart([b"ls", endpoint.encode("utf-8")])
            # time.sleep(1)
            # peers[c_tokens[2]]["soc"].send_multipart([b'Disconnect',int.to_bytes(int(c_tokens[1]),1,'big')])
        else:
            print("Unknown peer")
        continue

    if c.find("connect") != -1:
        # first is node origin
        # second is the node to connect to
        c_tokens: list[int] = c.split(" ")  # type: ignore
        try:
            for x in range(1, len(c_tokens)):
                c_tokens[x] = int(c_tokens[x])
            if len(c_tokens) < 3:
                raise ValueError
        except:
            print("Bad command")
            continue
        if c_tokens[1] in peers:
            inp = c_tokens[2]
            endpoint = f"tcp://127.0.0.1:8{inp}"

            peers[c_tokens[1]]["soc"].send_multipart(
                [b"Connect", endpoint.encode("utf-8")]
            )
            # time.sleep(1)
            # peers[c_tokens[2]]["soc"].send_multipart([b'Connect',int.to_bytes(int(c_tokens[1]),1,'big')])
        else:
            print("Unknown peer")
        continue

    # if c.find("sendc") != -1:
    #     # first is node origin
    #     # second is the node to connect to
    #     c_tokens: list[int] = c.split(" ")  # type: ignore
    #     try:
    #         for x in range(1, len(c_tokens)):
    #             c_tokens[x] = int(c_tokens[x])
    #         if len(c_tokens) < 2:
    #             raise ValueError
    #     except:
    #         print("Bad command")
    #         continue
    #     if c_tokens[1] in peers:
    #         peers[c_tokens[1]]["soc"].send_multipart(
    #             [b"SendData-C", int.to_bytes(int(c_tokens[2]), 1, "big")]
    #         )
    #     else:
    #         print("Unknown peer")
    #     continue

    if c.find("fsend") != -1:
        # first is node origin
        # second is the node to connect to
        c_tokens: list[int | str] = c.split(" ")  # type: ignore
        try:
            c_tokens[1] = int(c_tokens[1])
            if len(c_tokens) < 4:
                raise ValueError
        except:
            print("Bad command")
            continue
        if c_tokens[1] in peers:
            inp = c_tokens[2]
            peers[c_tokens[1]]["soc"].send_multipart(
                [b"SendData-F", inp.encode("utf-8"), c_tokens[3].encode("utf-8")]  # type: ignore
            )
        else:
            print("Unknown peer")
        continue

    if c.find("send") != -1:
        # first is node origin
        # second is the node to connect to
        c_tokens: list[int | str] = c.split(" ")  # type: ignore
        try:
            c_tokens[1] = int(c_tokens[1])
            if len(c_tokens) < 4:
                raise ValueError
        except:
            print("Bad command")
            continue
        if c_tokens[1] in peers:
            inp = c_tokens[2]
            peers[c_tokens[1]]["soc"].send_multipart(
                [b"SendData-D", inp.encode("utf-8"), c_tokens[3].encode("utf-8")]  # type: ignore
            )
        else:
            print("Unknown peer")
        continue

    if c.find("print") != -1:
        # first is node origin
        # second is the node to connect to
        c_tokens: list[int] = c.split(" ")  # type: ignore
        try:
            for x in range(1, len(c_tokens)):
                c_tokens[x] = int(c_tokens[x])
            if len(c_tokens) < 2:
                raise ValueError
        except:
            print("Bad command")
            continue
        if c_tokens[1] in peers:
            peers[c_tokens[1]]["soc"].send_multipart([b"print"])
        else:
            print("Unknown peer")
        continue

    if c.find("set") != -1:
        # first is node origin
        # second is the node to connect to
        c_tokens: tuple[str, int, str, str] = c.split(" ")  # type: ignore
        try:
            c_tokens[1] = int(c_tokens[1])
            if len(c_tokens) < 3:
                raise ValueError
        except:
            print("Bad command")
            continue

        if c_tokens[1] in peers:
            peers[c_tokens[1]]["soc"].send_multipart(
                [b"set", c_tokens[2].encode("utf-8"), c_tokens[3].encode("utf-8")]  # type: ignore
            )
        else:
            print("Unknown peer")
        continue

    print("Unknown command \n")
print("Done")
