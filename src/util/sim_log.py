import json
import os
import time
from typing import Optional
from dotenv import load_dotenv

from src.communications.main_pb2 import DHTSelect

load_dotenv()

MQTT_SERVER = os.getenv("MQTT_SERVER", "")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_USER = os.getenv("MQTT_USER", "")
MQTT_PWD = os.getenv("MQTT_PWD", "")


TURN_OFF_LOG = False

LOG_DHT_NODE_CREATE = "DHT_NODE_CREATE"
LOG_DHT_NODE_DELETE = "DHT_NODE_DELETE"
LOG_DHT_LOOKUP_START = "DHT_LOOKUP_START"
LOG_DHT_LOOKUP_OWNED = "DHT_LOOKUP_OWNED"
LOG_DHT_LOOKUP_NEIGHBOR = "DHT_LOOKUP_NEIGHBOR"
LOG_DHT_LOOKUP_NOTFOUND = "DHT_LOOKUP_NOTFOUND"
LOG_DHT_ADDRESS_UPDATE = "DHT_ADDRESS_UPDATE"
LOG_DHT_ADDRESS_DELETE = "DHT_ADDRESS_DELETE"
LOG_DHT_LOOKUP_CACHED = "DHT_LOOKUP_CACHED"

LOG_PROCESS_EVENT_SEND = "PROCESS_EVENT_SEND"
LOG_PROCESS_CHECKPOINT = "PROCESS_CHECKPOINT"
LOG_PROCESS_TASK_START = "PROCESS_TASK_START"
LOG_PROCESS_TASK_END = "PROCESS_TASK_END"
LOG_PROCESS_CLOSE_CHECKPOINT = "PROCESS_CLOSE_CHECKPOINT"

LOG_FILE_DATA_REQUEST = "FILE_DATA_REQUEST"
LOG_FILE_CHECKPOINT_SEND = "FILE_CHECKPOINT_SEND"
LOG_FILE_CLOSE_CHECKPOINT = "FILE_CLOSE_CHECKPOINT"
LOG_FILE_STORE = "FILE_STORE"

LOG_IO_REQUEST = "IO_REQUEST"
LOG_IO_STORE = "IO_STORE"

import string
import random

import paho.mqtt.client as mqtt


def generate_random_string(length=45):
    characters = (
        string.ascii_letters + string.digits
    )  # Includes uppercase, lowercase, and digits
    return "".join(random.choices(characters, k=length))


class SimLoggerHandler:
    def __init__(self, peerID):
        self.peerID = peerID
        if TURN_OFF_LOG:
            return
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.client.loop_start()
        self.client.username_pw_set(MQTT_USER, MQTT_PWD)
        self.client.connect(MQTT_SERVER, MQTT_PORT, 30)
        data = {"eventType": "START", "time": time.time()}
        self.client.publish(f"starfish/logs/{peerID}", json.dumps(data), 1)

    def start_session(self):
        if TURN_OFF_LOG:
            return ""
        return generate_random_string(10)

    def log(
        self,
        evt_type,
        peerFrom: Optional[bytes] = None,
        peerTo: Optional[bytes] = None,
        session=None,
        contentID=None,
        other=None,
        select=None,
    ):
        if session is None:
            session = ""
        data = {"time": time.time()}
        data["session"] = session
        data["eventType"] = evt_type
        if peerFrom is not None:
            data["peerFrom"] = peerFrom.hex(sep=":")
        if peerTo is not None:
            data["peerTo"] = peerTo.hex(sep=":")
        if contentID is not None:
            data["contentID"] = contentID.hex()
        if other is not None:
            data["other"] = other
        if select is not None and select == DHTSelect.PEER_ID:
            data["select"] = "PEER"
        if select is not None and select == DHTSelect.TASK_ID:
            data["select"] = "TASK"
        if select is not None and select == DHTSelect.FILE_ID:
            data["select"] = "FILE"
        if select is not None and select == DHTSelect.DEVICE_ID:
            data["select"] = "DEVICE"

        self.client.publish(f"starfish/logs/{self.peerID}", json.dumps(data))


sl = None


def SimLogger(item=None) -> SimLoggerHandler:
    global sl
    if sl is None and item is None:
        raise ValueError
    elif sl is None:
        sl = SimLoggerHandler(item.hex())
    return sl
