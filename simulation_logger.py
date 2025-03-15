import datetime
import json
import os
import sys
import time
import paho.mqtt.client as mqtt
import socket
from dotenv import load_dotenv
import sqlite3

from queue import Queue

load_dotenv()  # take environment variables from .env.


MQTT_SERVER = os.getenv("MQTT_SERVER", "")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_USER = os.getenv("MQTT_USER", "")
MQTT_PWD = os.getenv("MQTT_PWD", "")
HEARTBEAT = 10

msg_queue = Queue()


def on_connect(client: mqtt.Client, userdata, flags, reason_code, properties):
    # print(f"Connected with result code {reason_code}")
    # Subscribing in on_connect() means that if we lose the connection and
    # reconnect then subscriptions will be renewed.

    client.subscribe(f"starfish/logs/#")  # the '#' means wildcard of any subtopics.


def on_message(client, userdata, msg):
    # print(msg.topic + " " + str(msg.payload))
    if msg.payload == b"":
        return
    peerID = msg.topic.split("/")[-1]
    try:
        data = json.loads(msg.payload)
    except:
        pass
    data_out = (
        peerID,
        data.get("session"),
        data.get("eventType"),
        data.get("peerFrom"),
        data.get("peerTo"),
        data.get("contentID"),
        data.get("other"),
        data.get("select"),
        data.get("time"),
        time.time(),
    )
    msg_queue.put(data_out)


mqttc = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
mqttc.loop_start()

mqttc.on_connect = on_connect
mqttc.on_message = on_message
mqttc.username_pw_set(MQTT_USER, MQTT_PWD)
mqttc.connect(MQTT_SERVER, MQTT_PORT, 30)

dt = datetime.datetime.now()
timestamp = dt.strftime("%Y%m%d-%H%M%S")
db_filename = f"sim/simulation-data-{timestamp}.db"
conn = sqlite3.connect(db_filename)

cur = conn.cursor()
# Enable WAL mode for better durability
cur.execute("PRAGMA journal_mode=WAL;")

cur.execute(
    """CREATE TABLE "starlogs" (
	"logID"	INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    "peerID" TEXT,
	"sessionString"	TEXT,
	"eventType"	TEXT,
	"peerFrom"	TEXT,
	"peerTo"	TEXT,
	"contentID"	TEXT,
	"other"	TEXT,
	"selectTbl"	TEXT,
	"logtime"	REAL,
    "recvtime"  REAL
)"""
)

conn.commit()
counter = 0
last_time = time.time()

while True:
    try:
        msg = msg_queue.get()
        cur.execute(
            "INSERT INTO starlogs "
            "(peerID, sessionString, eventType, peerFrom, peerTo, contentID, other, selectTbl, logtime, recvtime) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            tuple(msg),
        )
        print(msg)
        counter += 1
        # if over 100 msgs or 2 seconds.
        if counter > 100 or time.time() - last_time > 2:
            conn.commit()
            last_time = time.time()
            counter = 0
    except KeyboardInterrupt:
        conn.commit()
        conn.close()
        break

mqttc.loop_stop()
