import json
import os
import sys
import docker
from docker.models.containers import Container
import time
import paho.mqtt.client as mqtt
import socket
from dotenv import load_dotenv

load_dotenv()  # take environment variables from .env.


class DockerOrchestrator:
    def __init__(self, pub_ip):
        try:
            self.client = docker.from_env()
        except:
            print("Is docker running???")
            sys.exit(2)
        self.public_ip = pub_ip

        self.running_peers: dict[bytes, dict[str, int | Container]] = {}

    def run(self, peer_address, os_port, io_port):
        print(f"Creating node: {peer_address.hex(sep=':')} os: {os_port} io: {io_port}")
        transport = f"tcp://{self.public_ip}:{os_port}"
        c_obj = self.client.containers.run(
            "starfishnode",
            auto_remove=True,
            detach=True,
            environment={
                "ADDRESS": f"{peer_address.hex(sep=':')}",
                "TRANSPORT": f"{transport}",
            },
            # ports: container_in : host
            ports={os_port: os_port, 2321: io_port},
        )

        self.running_peers[peer_address] = {
            "os": os_port,
            "io": io_port,
            "container": c_obj,
        }

    def stop(self, peer_address):
        print(f"Stopping node: {peer_address.hex(sep=':')}")
        self.running_peers[peer_address]["container"].stop()
        # self.running_peers[peer_address]["container"].remove()
        del self.running_peers[peer_address]

    def get_output(self, peer_address):
        container = self.running_peers[peer_address]["container"]
        return container.logs()

    def get_filestorage_list(self, peer_address):
        container = self.running_peers[peer_address]["container"]
        code, output = container.exec_run("ls filestorage/")
        return output.decode("utf-8").split("\n")


###################################################################

# USE MQTT Client.... (for worker processes)

# Register to the cloud that IP address exists
# starfish/ips/<IP>    = val

# listen for commands
# starfish/ips/<IP>/command = COMMAND.
# spawn peer with address
# kill peer
#
# RPC Sequence:
# Check if command is blank or ACK-123123.
#   Send command request... client then does the command and sets it to ACK-##
#
# starfish/ips/<IP>/peers/PEERID
# shows peer address, OS port, and IO port

MQTT_SERVER = os.getenv("MQTT_SERVER", "")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_USER = os.getenv("MQTT_USER", "")
MQTT_PWD = os.getenv("MQTT_PWD", "")
HEARTBEAT = 10


def get_my_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    my_ip = s.getsockname()[0]
    s.close()
    return my_ip


def is_port_in_use(port: int) -> bool:
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("localhost", port)) == 0


MY_IP = get_my_local_ip()

orchestra = DockerOrchestrator(MY_IP)

os_port_counter = 9280
io_port_counter = 2321


def on_connect(client: mqtt.Client, userdata, flags, reason_code, properties):
    # print(f"Connected with result code {reason_code}")
    # Subscribing in on_connect() means that if we lose the connection and
    # reconnect then subscriptions will be renewed.
    val = time.time()
    ip = MY_IP
    print(f"Publishing IP {ip}")
    client.publish(f"starfish/ips/{ip}", val, 1)  # don't retain this one.
    initial = {"command": "ack", "return": 0}
    client.publish(f"starfish/ips/{ip}/command", json.dumps(initial), 1, retain=True)

    client.subscribe(
        f"starfish/ips/{ip}/command"
    )  # the '#' means wildcard of any subtopics.


def on_message(client, userdata, msg):
    # print(msg.topic + " " + str(msg.payload))
    if msg.payload == b"":
        return
    if msg.topic == f"starfish/ips/{MY_IP}/command":
        run_command(client, msg.payload)


def run_command(client: mqtt.Client, command):
    s = command.decode("utf-8")
    c = json.loads(s)
    if c["command"] == "ack":
        return

    if c["command"] == "new":
        # create new
        create_node(client, c["peerID"])

    if c["command"] == "kill":
        # create new
        kill_node(client, c["peerID"])
    ret = 0
    if "return" in c:
        ret = c["return"]

    value = {"command": "ack", "return": ret}
    client.publish(f"starfish/ips/{MY_IP}/command", json.dumps(value), 1, retain=True)


def create_node(client: mqtt.Client, peerID):
    global os_port_counter
    global io_port_counter
    while is_port_in_use(os_port_counter):
        os_port_counter += 1
    while is_port_in_use(io_port_counter):
        io_port_counter += 1
    peer_address = bytes.fromhex(peerID)
    orchestra.run(peer_address, os_port_counter, io_port_counter)

    value = {"os": os_port_counter, "io": io_port_counter}
    # retain means when a later peer subscribes, they will be updated.
    client.publish(
        f"starfish/ips/{MY_IP}/peers/{peerID}", json.dumps(value), 1, retain=True
    )
    os_port_counter += 1
    io_port_counter += 1


def kill_node(client: mqtt.Client, peerID):
    peer_address = bytes.fromhex(peerID)
    try:
        orchestra.stop(peer_address)
    except:
        pass

    # retain means when a later peer subscribes, they will be updated.
    client.publish(
        f"starfish/ips/{MY_IP}/peers/{peerID}", "", 1, retain=True
    )  # clear topic


mqttc = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
mqttc.loop_start()

mqttc.on_connect = on_connect
mqttc.on_message = on_message
mqttc.username_pw_set(MQTT_USER, MQTT_PWD)
mqttc.connect(MQTT_SERVER, MQTT_PORT, 30)

while True:
    val = time.time()
    mqttc.publish(f"starfish/ips/{MY_IP}", val, 1)  # don't retain this one.
    time.sleep(HEARTBEAT)

mqttc.loop_stop()
