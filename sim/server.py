from flask import Flask, Response, send_file, request
import time
import os
import sqlite3
import json

import tqdm
import paho.mqtt.client as mqtt
from queue import Queue
from dotenv import load_dotenv

load_dotenv()

MQTT_SERVER = os.getenv("MQTT_SERVER", "")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_USER = os.getenv("MQTT_USER", "")
MQTT_PWD = os.getenv("MQTT_PWD", "")

STREAM_DELAY = 0.02
QUEUE_SIZE = 2000

msg_queue = Queue(int(QUEUE_SIZE * 1.5))

app = Flask(__name__)

# SIMULATION_DB = "test.db"
SIMULATION_DB = "simulation-data-20250317-183842.db"

# skips all log entries that are not this:
supported_events = set(
    [
        "START",
        "DHT_NODE_CREATE",
        "DHT_NODE_DELETE",
        "DHT_ADDRESS_UPDATE",
        "DHT_ADDRESS_DELETE",
        "DHT_LOOKUP_NEIGHBOR",
        "DHT_LOOKUP_NOTFOUND",
        "DHT_LOOKUP_OWNED",
        "PROCESS_TASK_START",
        "PROCESS_TASK_END",
        "PROCESS_EVENT_SEND",
        "PROCESS_CHECKPOINT_SEND",
        "FILE_DATA_REQUEST",
        "FILE_CHECKPOINT_SEND",
        "IO_REQUEST",
    ]
)

mission_critical = set(
    [
        "START",
        "DHT_NODE_DELETE",
        "DHT_NODE_CREATE",
        "DHT_ADDRESS_UPDATE",
        "DHT_ADDRESS_DELETE",
    ]
)

quoted_values = ", ".join([f"'{item}'" for item in supported_events])
where_clause = f"eventType IN ({quoted_values})"
logID_map = {}
logID_num = 1


@app.route("/")
def index():
    return send_file("index.html")


@app.route("/count_events")
def count_events():
    global logID_num
    global logID_map
    conn = sqlite3.connect(SIMULATION_DB)
    cur = conn.cursor()
    cur.execute(
        f"SELECT logID FROM starlogs WHERE (peerFrom != peerTo OR peerTo IS NULL OR peerFrom IS NULL) AND {where_clause}"
    )
    count = cur.fetchall()
    logID_map = {}
    logID_num = 1
    for logID in count:
        logID_map[logID_num] = logID[0]
        logID_num += 1
    conn.close()
    return str(len(logID_map))


@app.route("/event_stream")
def stream_events():
    def evt_stream():
        conn = sqlite3.connect(SIMULATION_DB)
        cur = conn.cursor()
        cur.execute(
            f"SELECT logID FROM starlogs WHERE (peerFrom != peerTo OR peerTo IS NULL OR peerFrom IS NULL) AND {where_clause}"
        )
        count = cur.fetchall()
        logIDs = []
        for logID in count:
            logIDs.append(logID[0])

        for i in tqdm.tqdm(logIDs):
            cur.execute(
                "SELECT peerID, eventType, peerFrom, peerTo, contentID, other, selectTbl FROM starlogs WHERE logID=?",
                (i,),
            )
            row = cur.fetchone()
            data = {
                "peerID": bytes.fromhex(row[0]).hex(sep=":"),
                "eventType": row[1],
                "peerFrom": row[2],
                "peerTo": row[3],
                "contentID": row[4],
                "other": row[5],
                "selectTbl": row[6],
            }
            yield f"data: {json.dumps(data)}\n\n"  # Correct SSE format
            time.sleep(STREAM_DELAY)
        conn.close()

    return Response(evt_stream(), mimetype="text/event-stream")


@app.route("/event_stream_live")
def stream_events_live():
    def evt_stream():
        print("Starting open live!")
        while True:
            data = msg_queue.get()
            yield f"data: {json.dumps(data)}\n\n"  # Correct SSE format
            time.sleep(STREAM_DELAY)

    return Response(evt_stream(), mimetype="text/event-stream")


@app.route("/event")
def get_event():
    conn = sqlite3.connect(SIMULATION_DB)
    cur = conn.cursor()
    evt = int(request.args.get("e")) + 1

    try:
        l = logID_map[evt]
    except:
        l = 0
    cur.execute(
        "SELECT peerID, eventType, peerFrom, peerTo, contentID, other, selectTbl FROM starlogs WHERE logID=?",
        (l,),
    )
    row = cur.fetchone()
    data = {
        "peerID": bytes.fromhex(row[0]).hex(sep=":"),
        "eventType": row[1],
        "peerFrom": row[2],
        "peerTo": row[3],
        "contentID": row[4],
        "other": row[5],
        "selectTbl": row[6],
    }
    conn.close()
    return json.dumps(data)


@app.route("/static/js/3d.js")
def static_js():
    return send_file("3d-force-graph.min.js")


#################
# MQTT
#################


def on_connect(client: mqtt.Client, userdata, flags, reason_code, properties):
    # print(f"Connected with result code {reason_code}")
    # Subscribing in on_connect() means that if we lose the connection and
    # reconnect then subscriptions will be renewed.

    client.subscribe(f"starfish/logs/#")  # the '#' means wildcard of any subtopics.


printed_flag = False
printed_flag2 = False
avg_rate = 0
time_since_last = time.time()
since_last_print = 0


def on_message(client, userdata, msg):
    global printed_flag
    global time_since_last
    global avg_rate
    global since_last_print
    global printed_flag2
    # print(msg.topic + " " + str(msg.payload))
    if msg.payload == b"":
        return
    peerID = msg.topic.split("/")[-1]
    try:
        data = json.loads(msg.payload)
    except:
        return

    evt = data.get("eventType")
    if evt is None:
        return

    if evt not in supported_events:
        return

    if data.get("peerFrom") == data.get("peerTo") and data.get("peerFrom") is not None:
        return

    data_out = {
        "peerID": bytes.fromhex(peerID).hex(sep=":"),
        "eventType": data.get("eventType"),
        "peerFrom": data.get("peerFrom"),
        "peerTo": data.get("peerTo"),
        "contentID": data.get("contentID"),
        "other": data.get("other"),
        "selectTbl": data.get("select"),
    }

    # overload handlers ....

    if msg_queue.qsize() > QUEUE_SIZE // 2 and not printed_flag:
        print(
            f"WARNING: QUEUE OVERRUN!!! Too many messages... {msg_queue.qsize()} Reducing...."
        )
        mps = 1000 / avg_rate
        print(f"Messages per second: {mps:.3f}")
        printed_flag = True

    if msg_queue.qsize() > QUEUE_SIZE // 4 and printed_flag:
        # unnecessary peer logs.
        if (
            data.get("select") == "PEER"
            and data.get("eventType") not in mission_critical
        ):
            return

    if msg_queue.qsize() > QUEUE_SIZE and not printed_flag2:
        print(
            f"WARNING: QUEUE OVERRUN!!! Dropped! Too many messages... {msg_queue.qsize()}"
        )
        mps = 1000 / avg_rate
        print(f"Messages per second: {mps:.3f}")
        printed_flag2 = True

    if msg_queue.qsize() > QUEUE_SIZE // 2 and printed_flag2:
        # mission critical
        if data.get("eventType") not in mission_critical:
            return

    msg_queue.put(data_out)
    if msg_queue.qsize() < QUEUE_SIZE // 2 and printed_flag2:
        print("Resume normal max")
        printed_flag2 = False
    if msg_queue.qsize() < QUEUE_SIZE // 4 and printed_flag:
        print("Resume normal soft")
        printed_flag = False

    delay = time.time() - time_since_last
    delay = delay * 1000
    avg_rate = avg_rate * 0.3 + delay * 0.7
    time_since_last = time.time()

    if time.time() > since_last_print + 10:
        mps = 1000 / avg_rate
        print(f"Avg live messages per second: {mps:.3f}   Q size: {msg_queue.qsize()}")
        since_last_print = time.time()


mqttc = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
mqttc.loop_start()

mqttc.on_connect = on_connect
mqttc.on_message = on_message
mqttc.username_pw_set(MQTT_USER, MQTT_PWD)
mqttc.connect(MQTT_SERVER, MQTT_PORT, 30)


if __name__ == "__main__":
    app.run(host="localhost", port=8008)
