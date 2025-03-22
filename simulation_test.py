from concurrent.futures import ThreadPoolExecutor
import os
import time

import tqdm
from src.util.util import gaussian_bytes
import matplotlib.pyplot as plt
from simulation_manager import PRUNE_TIME, SimulationOrchestrator
import networkx as nx
from pyvis.network import Network
import random

NUMBER_OF_PEERS_PER_IP = 1


def local_distribution(number_of_peers):
    maxval = (1 << 32) - 1  # max of 4 byte unsigned
    minval = 0

    step = int((maxval - minval) / number_of_peers)
    tick = 0
    out = []
    means = []

    print(f"Step size: {step}")
    for start in range(number_of_peers):
        mean = tick + step // 2
        tick += step
        std_dev = step // 4
        rand: bytes = gaussian_bytes(mean.to_bytes(4, "big"), std_dev, 4)
        r = int.from_bytes(rand, "big")
        if r < minval:
            r = minval + 1
        elif r > maxval:
            r = maxval - 1
        out.append(r)
        means.append(mean)
    return out, means


def generate_connected_graph(nodes):
    """
    Generates a random connected graph from a list of nodes.
    Ensures every node has a path to every other node.
    """
    G = nx.Graph()
    G.add_nodes_from(nodes)

    # Start with a spanning tree to ensure connectivity
    unvisited = set(nodes)
    current = unvisited.pop()
    visited = {current}

    while unvisited:
        next_node = unvisited.pop()
        # Connect the new node to a random visited node
        G.add_edge(current, next_node)
        visited.add(next_node)
        current = random.choice(list(visited))  # Move to another random visited node

    # Add extra random edges for more connectivity
    num_extra_edges = len(nodes) // 2  # Add approximately n/2 extra edges
    all_possible_edges = [(a, b) for a in nodes for b in nodes if a != b]
    existing_edges = set(G.edges)

    random.shuffle(all_possible_edges)
    for edge in all_possible_edges:
        if edge not in existing_edges and len(G.edges) < len(nodes) + num_extra_edges:
            G.add_edge(*edge)

    return G


def display_graph(graph):
    """
    Displays the given graph using NetworkX and Matplotlib.
    """
    plt.figure(figsize=(8, 6))
    pos = nx.spring_layout(graph)  # Compute layout for visualization
    labels = {node: node.hex(sep=":") for node in graph.nodes()}
    # nx.draw(
    #     graph,
    #     pos,
    #     with_labels=True,
    #     labels=labels,
    #     node_color="skyblue",
    #     edge_color="gray",
    #     node_size=500,
    #     font_size=8,
    # )
    # plt.show()

    # Create a Pyvis network
    net = Network(notebook=False)  # Set notebook=False if running outside Jupyter

    # Add nodes with labels
    for node in graph.nodes():
        net.add_node(node.hex(), label=node.hex(sep=":"))

    # Add edges
    for edge in graph.edges():
        net.add_edge(edge[0].hex(), edge[1].hex())

    net.show("graph.html", notebook=False)  # Opens in a browser


orchestrator = SimulationOrchestrator()
print("Discovering hosts....")
time.sleep(20)  # wait a moment to discover hosts....
ips = orchestrator.get_ips()
print(ips)
peers = orchestrator.get_peers()
print(peers)
if len(ips) == 0:
    input("No ips...")

input("Send out...")

ips = orchestrator.get_ips()
print(f"There are {len(ips)} ips")


total_number = NUMBER_OF_PEERS_PER_IP * len(ips)
out, means = local_distribution(total_number)

print(f"Initializing {total_number} peers")

fig, ax = plt.subplots(figsize=(10, 5))
for val in out:
    ax.axvline(x=val, color="blue", alpha=0.8, linewidth=1)
for mean in means:
    ax.axvline(x=mean, color="black", alpha=0.3, linewidth=1.5)

ax.set_xlim(0, (1 << 32) - 1)
ax.set_title("Random Number Distribution with Step Means")
ax.set_xlabel("Value Range (0 to 8-byte max)")
ax.set_ylabel("Density")
plt.show()

peer_connections = {}
for x in ips:
    peer_connections[x] = []  # or else there is hashing collisions

all_peers_to_ip = {}

# Start Peers

for peerCount in tqdm.tqdm(range(NUMBER_OF_PEERS_PER_IP)):
    for ip in ips:
        v: int = out.pop()
        peerID = v.to_bytes(4, "big") + os.urandom(4)
        peer_connections[ip].append(peerID)
        all_peers_to_ip[peerID] = ip
        print(f"Starting peer: {peerID.hex(sep=':')} to IP: {ip} ")
        orchestrator.run_node(ip, peerID)
        time.sleep(0.2)
        io_port = orchestrator.view_peer(peerID)["io"]
        print(f"Connect to {peerID.hex(sep=':')} at telnet://{ip}:{io_port}")

# peerID = bytes.fromhex("00:22:00:05:04:03:02:01".replace(":", ""))
# ip = "192.168.0.6"
# all_peers_to_ip[peerID] = ip
# orchestrator.run_node(ip, peerID)

# peerID = bytes.fromhex("18:00:00:00:00:00:00:00".replace(":", ""))
# ip = "192.168.0.7"
# all_peers_to_ip[peerID] = ip
# orchestrator.run_node(ip, peerID)

# peerID = bytes.fromhex("30:00:00:00:00:00:00:00".replace(":", ""))
# ip = "192.168.0.8"
# all_peers_to_ip[peerID] = ip
# orchestrator.run_node(ip, peerID)

# peerID = bytes.fromhex("48:00:00:00:00:00:00:00".replace(":", ""))
# ip = "192.168.0.9"
# all_peers_to_ip[peerID] = ip
# orchestrator.run_node(ip, peerID)

# Connect peers.
input("Connect???")

my_graph = generate_connected_graph(list(all_peers_to_ip.keys()))

display_graph(my_graph)


def connect(sourcePeer, targetPeer):
    source = all_peers_to_ip[sourcePeer]
    target = all_peers_to_ip[targetPeer]

    source_io_port = orchestrator.view_peer(sourcePeer)["io"]
    target_os_port = orchestrator.view_peer(targetPeer)["os"]
    target_transport = f"tcp://{target}:{target_os_port}"
    print(f"Peer connect {sourcePeer.hex(sep=':')} to {targetPeer.hex(sep=':')}")
    orchestrator.send_connect_command(
        source, source, source_io_port, targetPeer, target_transport
    )


for edge in tqdm.tqdm(my_graph.edges()):
    connect(edge[0], edge[1])

# source = bytes.fromhex("00:22:00:05:04:03:02:01".replace(":", ""))
# target = bytes.fromhex("18:00:00:00:00:00:00:00".replace(":", ""))
# connect(source, target)
# target = bytes.fromhex("30:00:00:00:00:00:00:00".replace(":", ""))
# connect(source, target)
# target = bytes.fromhex("48:00:00:00:00:00:00:00".replace(":", ""))
# connect(source, target)


input("Delete peers...")


def kill_nodes_of_ip(ip):
    for item in peer_connections[ip]:
        print(f"Killing node {item.hex(sep=':')} on ip: {ip}")
        orchestrator.kill_node(ip, item, prune=False)
    return 0


with ThreadPoolExecutor(max_workers=len(ips)) as exe:
    # Maps the method 'cube' with a list of values.
    for ip in peer_connections:
        result = exe.submit(kill_nodes_of_ip, ip)


# orchestrator.kill_node(
#     "192.168.0.6", bytes.fromhex("00:22:00:05:04:03:02:01".replace(":", ""))
# )
# orchestrator.kill_node(
#     "192.168.0.7", bytes.fromhex("18:00:00:00:00:00:00:00".replace(":", ""))
# )
# orchestrator.kill_node(
#     "192.168.0.8", bytes.fromhex("30:00:00:00:00:00:00:00".replace(":", ""))
# )
# orchestrator.kill_node(
#     "192.168.0.9", bytes.fromhex("48:00:00:00:00:00:00:00".replace(":", ""))
# )

orchestrator.stop()
