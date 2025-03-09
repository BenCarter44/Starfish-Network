import json
import os
import random
import time

from src.util.util import gaussian_bytes
import matplotlib.pyplot as plt

import paho.mqtt.client as mqtt
from dotenv import load_dotenv
import re
import threading

load_dotenv()  # take environment variables from .env.


##### Manager
# Subscribe to all starfish/ips/##
# Scan for IPs that are older than 30 seconds. If so, clean up records.
# Send new/kill commands
#
# List all Peers.
# List all IPs
# Retrieve Peer IO port


MQTT_SERVER = os.getenv("MQTT_SERVER", "")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_USER = os.getenv("MQTT_USER", "")
MQTT_PWD = os.getenv("MQTT_PWD", "")
PRUNE_TIME = 60


class SimulationOrchestrator:
    def __init__(self):

        self.known_ips: dict[str, float] = {}
        self.known_peers: dict[str, dict[str, int | str | float]] = {}
        self.known_command: dict[str, float] = {}
        self.command_data: dict[str, dict[str, int | bool]] = {}

        mqttc = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        mqttc.loop_start()

        mqttc.on_connect = lambda a, b, c, d, e: self.on_connect(a, b, c, d, e)
        mqttc.on_message = lambda a, b, c: self.on_message(a, b, c)
        mqttc.username_pw_set(MQTT_USER, MQTT_PWD)
        mqttc.connect(MQTT_SERVER, MQTT_PORT, 30)
        self.client = mqttc

        th_prune = threading.Thread(None, target=self.prune_task)
        th_prune.start()
        self.is_stopping = False

    def on_connect(self, client, userdata, flags, reason_code, properties):
        self.client.subscribe(f"starfish/ips/#")

    def is_ip_root(self, s: str) -> bool:
        pattern = r"^starfish\/ips\/(?:(?:25[0-5]|2[0-4][0-9]|1?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|1?[0-9][0-9]?)$"
        return re.fullmatch(pattern, s) is not None

    def is_peer_msg(self, s: str) -> bool:
        pattern = r"^starfish\/ips\/(?:(?:25[0-5]|2[0-4][0-9]|1?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|1?[0-9][0-9]?)\/peers\/"
        return re.match(pattern, s) is not None

    def is_command_msg(self, s: str) -> bool:
        pattern = r"^starfish\/ips\/(?:(?:25[0-5]|2[0-4][0-9]|1?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|1?[0-9][0-9]?)\/command"
        return re.match(pattern, s) is not None

    def on_message(self, client, userdata, msg):
        # print(msg.topic + " " + str(msg.payload))
        if msg.payload == b"" and self.is_peer_msg(msg.topic):
            # peer message delete
            peerID = msg.topic.split("/")[-1]
            if peerID in self.known_peers:
                del self.known_peers[peerID]
            return
        elif msg.payload == b"":
            return

        if self.is_ip_root(msg.topic):
            ip = msg.topic.split("/")[-1]
            self.known_ips[ip] = float(msg.payload.decode("utf-8"))
            return

        elif self.is_peer_msg(msg.topic):
            peerID = msg.topic.split("/")[-1]
            ip = msg.topic.split("/")[-3]
            s = json.loads(msg.payload.decode("utf-8"))
            self.known_peers[peerID] = {
                "ip": ip,
                "os": s["os"],
                "io": s["io"],
                "time": time.time(),
            }

        elif self.is_command_msg(msg.topic):
            ip = msg.topic.split("/")[-2]
            self.known_command[ip] = time.time()
            command = json.loads(msg.payload.decode("utf-8"))
            self.command_data[ip] = {
                "available": command["command"] == "ack",
                "return": command["return"],
            }

    def prune(self):
        ips = []
        to_delete = []
        for ip, last_seen in self.known_ips.items():
            if last_seen < time.time() - PRUNE_TIME:
                # old!
                item = f"starfish/ips/{ip}"
                self.client.publish(item, "", 1)
                to_delete.append(ip)
            else:
                ips.append(ip)

        for x in to_delete:
            del self.known_ips[x]

        to_delete = []
        for x, t in self.known_command.items():
            if x not in self.known_ips and t < time.time() - PRUNE_TIME:
                item = f"starfish/ips/{x}/command"
                self.client.publish(item, "", 1, retain=True)
                to_delete.append(x)
                del self.command_data[x]

        for x in to_delete:
            del self.known_command[x]

        to_delete = []

        for peer, value in self.known_peers.items():
            if value["ip"] not in ips and value["time"] < time.time() - PRUNE_TIME:
                ip = value["ip"]
                item = f"starfish/ips/{ip}/peers/{peer}"
                self.client.publish(item, "", 1, retain=True)
                to_delete.append(peer)

        for x in to_delete:
            del self.known_peers[x]

    def run_node(self, ip, peerID):
        while not (self.command_data[ip]["available"]):
            time.sleep(0.1)

        ret = random.randint(1, (2**32) - 1)
        val = {"command": "new", "peerID": peerID.hex(), "return": ret}

        self.client.publish(f"starfish/ips/{ip}/command", json.dumps(val), 2)
        while not (
            self.command_data[ip]["available"]
            and self.command_data[ip]["return"] == ret
        ):
            time.sleep(0.1)

    def kill_node(self, ip, peerID):
        while not (self.command_data[ip]["available"]):
            time.sleep(0.1)

        ret = random.randint(1, (2**32) - 1)
        val = {"command": "kill", "peerID": peerID.hex(), "return": ret}

        self.client.publish(f"starfish/ips/{ip}/command", json.dumps(val), 2)
        while not (
            self.command_data[ip]["available"]
            and self.command_data[ip]["return"] == ret
        ):
            time.sleep(0.1)
        self.prune()

    def view_peer(self, peer):
        return self.known_peers[peer.hex()]

    def get_ips(self):
        return list(self.known_ips.keys())

    def get_peers(self):
        return list(self.known_peers.keys())

    def prune_task(self):
        time.sleep(PRUNE_TIME)
        while True:
            time.sleep(1)
            if self.is_stopping:
                break
            self.prune()

    def stop(self):
        self.is_stopping = True
        self.client.loop_stop()


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


# number_of_peers = 4000
# outs, means = local_distribution(number_of_peers)

# fig, ax = plt.subplots(figsize=(10, 5))
# for val in outs:
#     ax.axvline(x=val, color="blue", alpha=0.8, linewidth=1)
# for mean in means:
#     ax.axvline(x=mean, color="black", alpha=0.3, linewidth=1.5)

# ax.set_xlim(0, (1 << 32) - 1)
# ax.set_title("Random Number Distribution with Step Means")
# ax.set_xlabel("Value Range (0 to 8-byte max)")
# ax.set_ylabel("Density")
# plt.show()


orchestrator = SimulationOrchestrator()
time.sleep(12)  # wait a moment to discover hosts....
ips = orchestrator.get_ips()
print(ips)
p = os.urandom(8)
orchestrator.run_node(ips[0], p)
peers = orchestrator.get_peers()
print(peers)
input("Wait to kill....")
orchestrator.kill_node(ips[0], p)
print("Done")

peers = orchestrator.get_peers()
print(peers)

orchestrator.stop()
