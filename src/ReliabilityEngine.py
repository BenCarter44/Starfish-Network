import threading
from typing import Any, List, Optional
import time

import zmq
from src.utils import dump, zpipe


class ReliableMessage:
    """Reliable message struct"""

    def __init__(self, data: Any, retry_gap: float, max_retry: Optional[int]):
        """Create message

        Args:
            data (Any): Message to send
            retry_gap (int): Length of seconds between retries
            max_retry (Optional[int]): Max retries
        """
        self.data = data
        self.status: bool = False
        self.retry_gap = retry_gap
        self.max_retry = max_retry

    def mark_done(self):
        """Mark reliable message as done"""
        self.status = True

    def is_complete(self) -> bool:
        """See if message is complete

        Returns:
            bool: True if complete
        """
        return self.status


class ReliabilityEngine:
    """Reliable "lazy-pirate" socket"""

    def __init__(
        self, ctx: zmq.Context, socket: zmq.Socket, output: zmq.Socket
    ) -> None:
        """Create socket

        Args:
            ctx (zmq.Context): ZMQ Context
            socket (zmq.Socket): ZMQ Socket to take ownership and act on behalf of
            output (zmq.Socket): ZMQ Socket PIPE that sends out messages from owned socket
        """

        self.timer: List[float] = []
        self.msg_objects: List[ReliableMessage] = []
        self.signal = threading.Event()
        self.signal.clear()
        self.is_stop = False
        self.peers = 0

        self.th = threading.Thread(
            None, self.__replay_management, name="Reliability Engine Thread"
        )
        self.th.start()

        self.control_pipe, pipe = zpipe(ctx)

        self.th2 = threading.Thread(
            None,
            self.__socket_management,
            args=(pipe, output, socket),
            name="Reliablity Socket Thread",
        )
        self.th2.start()

        self.pending_tasks = 0
        self.output_socket = output

        self.verified_peers = 0

    def __socket_management(
        self, pipe: zmq.Socket, output: zmq.Socket, primary: zmq.Socket
    ):
        """Thread managing socket

        Args:
            pipe (zmq.Socket): Internal Control PIPE
            output (zmq.Socket): Socket PIPE to send output to
            primary (zmq.Socket): Owned socket under manipulation
        """
        poller = zmq.Poller()
        poller.register(pipe, zmq.POLLIN)
        poller.register(primary, zmq.POLLIN)

        while True:
            socket_receiving = dict(poller.poll(1000))
            if pipe in socket_receiving:
                i = pipe.recv_multipart()
                # dump(i)
                # print('-')
                if i[0] == b"STOP STOP STOP RE ENGINE":
                    break
                if i[0] == b"RE ENGINE connect":
                    # print("Connected")
                    primary.connect(i[1].decode("utf-8"))
                    self.verified_peers += 1
                elif i[0] == b"RE ENGINE disconnect":
                    # print("Disconnected")
                    primary.disconnect(i[1].decode("utf-8"))
                    self.verified_peers -= 1

                    if self.peers > 0:
                        self.peers -= 1
                else:
                    # print("Send: ",i)
                    # for x in range(self.verified_peers): # TODO. DEALER distributes requests
                    primary.send_multipart(i)

            if primary in socket_receiving:
                i = primary.recv_multipart()
                output.send_multipart(i)

    def get_number_pending(self) -> int:
        """Get number of messages in queue

        Returns:
            int: Number pending tasks
        """
        return self.pending_tasks

    def get_number_peers(self) -> int:
        """Get number of connected and verified peers

        Returns:
            int: Number peers
        """
        return self.verified_peers

    def add_peer(self, endpoint: str):
        """Add and connect to peer... like socket.connect()

        Args:
            endpoint (str): Endpoint
        """
        # print("connect")
        self.peers += 1
        self.add_message([b"RE ENGINE connect", endpoint.encode("utf-8")], max_retry=1)

    def remove_peer(self, endpoint: str):
        """Disconnect from peer... like socket.disconnect()

        Args:
            endpoint (str): Endpoint
        """
        # print("Disc")
        self.add_message(
            [b"RE ENGINE disconnect", endpoint.encode("utf-8")], max_retry=1
        )

    def __add_to_timer(self, time_fire: float, msg: ReliableMessage):
        """Add message to timer queue

        Args:
            time_fire (float): time message must be sent
            msg (ReliableMessage): message to send
        """
        count = 0
        while count < len(self.timer) and self.timer[count] < time_fire:
            count += 1

        self.timer.insert(count, time_fire)
        self.msg_objects.insert(count, msg)
        self.signal.set()
        # print("Added to timer")
        # print("QUEUE: ",self.timer)

    def add_message(
        self,
        message: List[bytes],
        retry_gap: float = 10,
        max_retry: Optional[int] = None,
    ) -> Optional[ReliableMessage]:
        """Add message to internal queues

        Args:
            message (List[bytes]): Multipart message
            retry_gap (float): Length of seconds between retries. Defaults to 10.
            max_retry (int, optional): Max number of retries. Defaults to keep trying forever.

        Returns:
            Optional[ReliableMessage]: ReliableMessage struct keeping track of message. None if no message sent out
        """
        if max_retry is not None and max_retry <= 0:
            return None
        if self.peers == 0:
            return None  # drop if no one to send to!

        # print(f"Sent message: {message}. Time: {time.time() % 240} Remaining: {self.pending_tasks}")
        msg = ReliableMessage(message, retry_gap, max_retry)
        # print("MESSAGE  : ",msg.data)
        self.__add_to_timer(0, msg)  # send immediately!
        self.pending_tasks += 1

        self.__add_to_timer(retry_gap + time.time(), msg)
        self.pending_tasks += 1
        return msg

    def add_message_delay(
        self, message: List[bytes], delay=1, retry_gap: int = 10, max_retry=None
    ) -> Optional[ReliableMessage]:
        """Add message to internal queues with initial delay

        Args:
            message (List[bytes]): Multipart message.
            delay (int) : Delay time in seconds. Defaults to 10.
            retry_gap (int): Length of seconds between retries. Defaults to 10.
            max_retry (int, optional): Max number of retries. Defaults to keep trying forever.

        Returns:
            Optional[ReliableMessage]: ReliableMessage struct keeping track of message. None if no message sent out
        """
        if max_retry is not None and max_retry <= 0:
            return None
        if self.peers == 0:
            return None  # drop if no one to send to!

        # print(f"Sent message: {message}. Time: {time.time() % 240} Remaining: {self.pending_tasks}")
        msg = ReliableMessage(message, retry_gap, max_retry)
        # print("MESSAGE  : ",msg.data)
        self.__add_to_timer(time.time() + delay, msg)  # send immediately!
        self.pending_tasks += 1

        self.__add_to_timer(retry_gap + time.time() + delay, msg)
        self.pending_tasks += 1
        return msg

    def __add_message_RM(self, msg: ReliableMessage) -> Optional[ReliableMessage]:
        """Internal thread execute message

        Args:
            msg (ReliableMessage): Reliable Message Struct

        Returns:
            Optional[ReliableMessage]: Modified Message Struct or None if no message sent
        """
        # print("RM: ", msg.max_retry)
        if msg.max_retry is not None and msg.max_retry <= 0:
            return None
        if msg.max_retry is not None:
            msg.max_retry -= 1
        # print('Retry')
        if self.peers == 0:
            return None  # drop if no one to send to!
        self.control_pipe.send_multipart(msg.data)
        # print(f"Sent message: {msg.data}. Remain: {self.pending_tasks}")
        self.__add_to_timer(msg.retry_gap + time.time(), msg)
        self.pending_tasks += 1
        return msg

    def stop(self):
        """Stop thread. There is no going back!"""
        self.is_stop = True
        self.signal.set()
        self.th.join()

    def __replay_management(self):
        """Internal thread managing the timer"""
        while True:
            wait_start = time.time()
            if len(self.timer) == 0:
                self.signal.wait()
            else:
                w = self.timer[0] - time.time()
                if w > 0:
                    self.signal.wait(w)

            if self.is_stop:
                self.control_pipe.send_multipart([b"STOP STOP STOP RE ENGINE"])
                break

            wait_end = time.time()
            self.timer[0] = self.timer[0] - (wait_end - wait_start)
            # print(f"Time Remaining: {(time.time() - self.timer[0]) % 240}.")
            # print("MESSAGE-r: ",self.msg_objects[0].data, self.timer[0])
            if self.timer[0] < time.time():
                msg = self.msg_objects[0]
                if not (msg.is_complete()):
                    # print("PIzza@")
                    self.__add_message_RM(msg)
                self.timer.pop(0)
                self.msg_objects.pop(0)
                self.pending_tasks -= 1

            self.signal.clear()
