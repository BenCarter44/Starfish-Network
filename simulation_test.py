import os
import time
from src.util.util import gaussian_bytes
import matplotlib.pyplot as plt
from simulation_manager import SimulationOrchestrator


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


orchestrator = SimulationOrchestrator()
print("Discovering hosts....")
time.sleep(10)  # wait a moment to discover hosts....
ips = orchestrator.get_ips()
print(ips)
peers = orchestrator.get_peers()
print(peers)

ips = orchestrator.get_ips()
print(f"There are {len(ips)} ips")


number_of_peers_per_ip = 8
total_number = number_of_peers_per_ip * len(ips)
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


for peerCount in range(number_of_peers_per_ip):
    for ip in ips:
        v: int = out.pop()
        peerID = v.to_bytes(4, "big") + os.urandom(4)
        print(f"Starting peer: {peerID.hex(sep=':')} to IP: {ip}")
        orchestrator.run_node(ip, peerID)

orchestrator.stop()
