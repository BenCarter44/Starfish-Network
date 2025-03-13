import os
from queue import Queue
import threading
import time
from typing import Optional
import urllib3
from dotenv import load_dotenv

from src.communications.main_pb2 import DHTSelect

load_dotenv()

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


class SimLoggerHandler:
    def __init__(self):
        self.queue = Queue()
        self.is_running = False
        self.th = threading.Thread(None, target=self.run)
        self.http = urllib3.PoolManager()

        self.queue_pre_sessions = Queue(10)
        self.th2 = threading.Thread(None, target=self.run_pre_session)

    def run(self):
        while True:
            item = self.queue.get()
            self.run_log(*item)

    def run_pre_session(self):
        while True:
            self.queue_pre_sessions.put(self.run_start_session())

    def start_session(self):
        if TURN_OFF_LOG:
            return ""
        clock = time.time()
        if not (self.is_running):
            self.th.start()
            self.th2.start()
            self.is_running = True
        s = self.queue_pre_sessions.get()
        # print(f"Time waiting for session: {(time.time() - clock) * 1000}")
        return s

    def run_start_session(self):
        response = self.http.request(
            "POST",
            os.getenv("START_SESSION_URL"),
            fields={"key": os.getenv("SIM_LOGGER_KEY")},
        )
        sessionID = response.data.decode("utf-8")
        return sessionID

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
        if TURN_OFF_LOG:
            return
        clock = time.time()
        if not (self.is_running):
            self.th.start()
            self.th2.start()
            self.is_running = True
        item = (evt_type, peerFrom, peerTo, session, contentID, other, select)
        self.queue.put(item)
        # print(f"Time waiting for log: {(time.time() - clock) * 1000}")

    def run_log(
        self,
        evt_type,
        peerFrom: Optional[bytes] = None,
        peerTo: Optional[bytes] = None,
        session=None,
        contentID=None,
        other=None,
        select=None,
    ):
        if session == "":
            session = None
        if session is None:
            session = self.start_session()

        data = {"key": os.getenv("SIM_LOGGER_KEY")}
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

        response = self.http.request(
            "POST",
            os.getenv("SIM_LOGGER_URL"),
            fields=data,
        )
        if response.data != b"good":
            raise ValueError(response.data)


sl = SimLoggerHandler()


def SimLogger() -> SimLoggerHandler:
    return sl
