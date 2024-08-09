import time
from typing import Optional
from typing_extensions import Any, List, Self, Tuple

from src.ttl import DataTTL
from src.utils import dump
import struct
import dill

ALLOWED_TIME_OFFSET = 10.0


def float_to_bytes(f: float) -> bytes:
    """Convert float/double to a bytes struct of just the float

    Args:
        f (float): float

    Returns:
        bytes: float (as double) in bytes
    """
    return struct.pack("d", f)


def bytes_to_float(b: bytes) -> float:
    """Convert bytes to float. Assumes double

    Args:
        b (bytes): bytes

    Returns:
        float: float
    """
    return struct.unpack("d", b)[0]


class BasicMultipartMessage:
    """The parent class of all messages"""

    def __init__(self):
        """Init a basic bare message"""

        self.data = [
            b"TOPIC",
            b"SUB TOPIC",
            b"Reply Identity",
            b"Compile Time",
            b"Number of Data Messages",
            b"Data",
            # b'Data',
            # ...
        ]
        self.data = [b""] * len(self.data)

    def set_topic(self, topic: str):
        """Set message topic

        Args:
            topic (str): Topic
        """
        self.data[0] = topic.encode("utf-8")

    def set_subtopic(self, subtopic: str):
        """Set message subtopic

        Args:
            subtopic (str): Subtopic
        """
        self.data[1] = subtopic.encode("utf-8")

    def set_val(self, val: bytes):
        """Set a single value

        Args:
            val (bytes): Value
        """
        self.data[4] = int.to_bytes(1, 2, "big")
        self.data[5] = val

    def set_val_multiple(self, vals: list[bytes]):
        """Set a list of values

        Args:
            val (bytes): Value
        """
        if len(vals) == 0:
            return
        self.data[4] = int.to_bytes(len(vals), 2, "big")
        self.data = self.data[:5]  # chop off all values.
        for x in vals:
            self.data.append(x)

    def get_topic(self) -> str:
        """Get message topic

        Returns:
            str: Topic
        """
        return self.data[0].decode("utf-8")

    def get_subtopic(self) -> str:
        """Get message subtopic

        Returns:
            str: Subtopic
        """
        return self.data[1].decode("utf-8")

    def get_compile_time(self) -> float:
        """Get Message Compile Timestamp

        Returns:
            float: Timestamp that message was compiled
        """
        return bytes_to_float(self.data[3])

    def get_reply_identity(self) -> int:
        """Get the reply identity of the message

        Returns:
            int: Reply identity of message
        """
        return int.from_bytes(self.data[2], "big")

    def get_val(self) -> bytes:
        """Get value of message

        Returns:
            bytes: The value of the message
        """
        return self.data[5]

    def get_multiple_values(self) -> list[bytes]:
        """Get the series of values

        Returns:
            list[bytes]: Series of values
        """
        amount = int.from_bytes(self.data[4], "big")
        out = []
        for x in range(amount):
            out.append(self.data[5 + x])
        return out

    def compile(self, reply_id: int = 0) -> list[bytes]:
        """Get raw multipart message

        Args:
            reply_id (int, optional): Specify reply identifier. Default 0.
        Returns:
            list[bytes]: Multipart message
        """
        self.data[2] = int.to_bytes(reply_id, 2, "big")
        self.data[3] = float_to_bytes(time.time())
        return self.data

    def import_msg(self, data_in: list[bytes]):
        """Import multipart message

        Args:
            data_in (list[bytes]): multipart message

        Raises:
            ValueError - Malformed message
            TimeoutError - Messuage sent in the future
        """
        if len(data_in) <= 5:
            raise ValueError("Malformed message")

        timestamp = bytes_to_float(data_in[3])
        if timestamp > time.time() + ALLOWED_TIME_OFFSET:
            raise TimeoutError("Message was sent in the future. Malformed")

        self.data = data_in

    def compile_with_address(self, addr: bytes | int, reply_id: int = 0) -> list[bytes]:
        """Return multipart message with address

        Args:
            addr (bytes): Address to add to message
            reply_id (int, optional): Specify reply identifier. Default 0.

        Returns:
            List[bytes]: multipart message
        """
        if isinstance(addr, int):
            addr = int.to_bytes(addr, 4, "big")
        d = self.compile(reply_id=reply_id)
        d.insert(0, addr)
        return d


class PeerKV(BasicMultipartMessage):
    """General Peer KeyValue Exchange Messages

    Inherits:
        BasicMultipartMessage
    """

    def __init__(self):
        """Initiate message."""
        super(PeerKV, self).__init__()
        self.set_topic("General")

    def fetch_state_command(self):
        """Create a fetch-state message

        Args:
            r_identity (int): Reply identity
        """
        self.set_topic("General")
        self.set_subtopic("fetch_state")

    def is_fetch_state(self) -> bool:
        """See if message is a fetch-state message

        Returns:
            bool: True if fetch-state message
        """
        return self.get_subtopic() == "fetch_state"

    def is_return_state(self) -> bool:
        """See if message is a return-state message

        Returns:
            bool: True if return-state message
        """
        return self.get_subtopic() == "return_state"

    def is_push_change(self) -> bool:
        """See if message is a push-change message

        Returns:
            bool: True if a push-change message
        """
        return self.get_subtopic() == "push_change"

    def is_push_change_receive(self) -> bool:
        """See if message is a push-change-receive message

        Returns:
            bool: True if a push-change-receive message
        """
        return self.get_subtopic() == "push_change_receive"

    def is_requesting_connection(self) -> bool:
        """See if message is a requesting-connection message

        Returns:
            bool: True if a requesting-connection message
        """
        return self.get_subtopic() == "request_connection"

    def is_requesting_connection_feedback(self) -> bool:
        """See if message is a request-connection-feedback message

        Returns:
            bool: True if message is a request-connection-feedback message
        """
        return self.get_subtopic() == "request_connection_ok"

    def is_requesting_disconnection(self) -> bool:
        """See if message is a request-disconnection message

        Returns:
            bool: True if message is a request-disconnection message
        """
        return self.get_subtopic() == "request_disconnection"

    def request_disconnect(self):
        """Create request-disconnect message"""
        self.set_topic("General")
        self.set_subtopic("request_disconnection")

    def request_connection_cmd(self):
        """Create request-connection message"""
        self.set_topic("General")
        self.set_subtopic("request_connection")

    def request_connection_feedback(self):
        """Create request-connection-feedback message

        Args:
            r_identity (int): Reply identity
        """
        self.set_topic("General")
        self.set_subtopic("request_connection_ok")

    def return_state_receipt(self, values: List[Tuple[str, DataTTL]]):
        """Create state-return message

        Args:
            values (List[Tuple[str, DataWithTTL]]): Keys with values - keyvalue store
        """
        self.set_topic("General")
        self.set_subtopic("return_state")
        out: list[bytes] = []
        for x in values:
            out.append(x[0].encode("utf-8"))  # key
            out.append(x[1].to_bytes())  # DataWithTTL Object

        self.set_val_multiple(out)

    def push_change(self, key: str, value: DataTTL):
        """Push single change message

        Args:
            key (str): key
            value (DataWithTTL): value with ttl management
        """
        self.set_topic("General")
        self.set_subtopic("push_change")
        self.set_val_multiple([key.encode("utf-8"), value.to_bytes()])

    def get_push_key_val(self) -> tuple[str, DataTTL]:
        """Get key value from message created by push_change

        Returns:
            str: key
            DataWithTTL: value
        """
        vals = self.get_multiple_values()
        dt = DataTTL(None, 0, True)
        dt.from_bytes(vals[1])
        return vals[0].decode("utf-8"), dt

    def return_push_change(self):
        """Create return-push-change"""
        self.set_topic("General")
        self.set_subtopic("push_change_receive")

    def get_state_from_return(self) -> List[Tuple[str, DataTTL]]:
        """Load state from message created by return_state_receipt

        Returns:
            List[Tuple[str, DataWithTTL]]: keyvalue state
        """
        assert self.get_subtopic() == "return_state"

        vals = self.get_multiple_values()

        length = len(vals) // 2

        out: list[tuple[str, DataTTL]] = list(range(length))  # type: ignore
        # assumes length is not lying, telling the truth

        for x in range(length):
            dt = DataTTL(None, 0, True)
            dt.from_bytes(vals[x * 2 + 1])
            out[x] = (vals[x * 2].decode("utf-8"), dt)
        return out

    def import_msg(self, data_in: list[bytes]):
        """Import message and check if valid

        Args:
            data_in (list[bytes]): Imported Message

        Raises:
            ValueError: Malformed message
        """
        super(PeerKV, self).import_msg(data_in)
        if self.get_topic() != "General":
            raise ValueError("Not a PeerKV Message")

    def is_error_msg(self) -> bool:
        """See if error message

        Returns:
            bool: True if error message
        """
        return self.get_subtopic() == "Error"

    def get_error_code(self) -> tuple[int, str]:
        """Get error code and value

        Returns:
            tuple[int, str]: error number and value
        """
        vals = self.get_multiple_values()
        return int.from_bytes(vals[0], "big"), vals[1].decode("utf-8")

    def error_feedback(self, code: int, cmd: str):
        """Create error message

        Args:
            code (int): Error code
            cmd (str): Error value
            r_identity (int): Reply Identity
        """
        self.set_topic("General")
        self.set_subtopic("Error")
        self.set_val_multiple([int.to_bytes(code, 2, "big"), cmd.encode("utf-8")])


class PeerKV_Hello(PeerKV):
    """Hello sequence of messages

    Inherits:
        PeerKV
    """

    def __init__(self):
        """Setup object"""
        super(PeerKV_Hello, self).__init__()

    def create(self, serving_endpoint_query: str):
        """Create hello message

        Args:
            serving_endpoint_query (str): Endpoint
        """
        self.set_topic("Hello!")
        self.set_subtopic("key_update")
        self.set_val(serving_endpoint_query.encode("utf-8"))

    def create_welcome(self):
        """Create welcome message"""
        self.set_topic("Welcome Home son!")
        self.set_subtopic("For you were lost, but now you're found")

    def import_msg(self, data_in: list[bytes]):
        """Import message and check if valid Hello Message

        Args:
            data_in (list[bytes]): Imported Message

        Raises:
            ValueError: Malformed message
        """
        super(PeerKV, self).import_msg(data_in)
        if self.get_topic() != "Hello!" and self.get_topic() != "Welcome Home son!":
            raise ValueError("Not a Hello Message")

    def get_endpoint(self) -> str:
        """Get hello endpoint

        Returns:
            str: endpoint
        """
        return self.get_val().decode("utf-8")


class Datagram:
    """For Data Passing"""

    def __init__(
        self,
        to: int,
        data: Any | Self,
        comm_id: Optional[int] = None,
        packet: Optional[int] = None,
        term: bool = False,
        exp_len: Optional[int] = None,
        author: Optional[int] = None,
        resend: bool = False,
    ):

        d = b""
        if isinstance(data, bytes):
            d = data
            t = b"0"
        else:
            d = dill.dumps(data)
            t = b"1"

        comm_bytes = b""
        if comm_id is not None:
            comm_bytes = int.to_bytes(comm_id, 4, "big")

        packet_bytes = b""
        if packet is not None:
            packet_bytes = int.to_bytes(packet, 4, "big")

        term_bytes = b"0"
        if term:
            term_bytes = b"1"

        resend_bytes = b"0"
        if resend:
            resend_bytes = b"1"

        exp_bytes = b""
        if exp_len is not None:
            exp_bytes = int.to_bytes(exp_len, 4, "big")

        author_bytes = b""
        if author is not None:
            author_bytes = int.to_bytes(author, 4, "big")

        self.data: list[bytes] = [
            int.to_bytes(to, 4, "big"),
            b"hash",
            d,
            t,
            comm_bytes,
            packet_bytes,
            term_bytes,
            exp_bytes,
            author_bytes,
            resend_bytes,
        ]

    def __str__(self):
        c, p = self.get_ids()
        return f"<Datagram: {c} #{p} - Carrying data: L: {len(self.data[2])}>"

    def is_term(self):
        return self.data[6] == b"1"

    def get_data(self):
        if self.data[3] == b"0":
            return self.data[2]
        else:
            return dill.loads(self.data[2])

    def get_author(self):
        if self.data[8] != b"":
            return int.from_bytes(self.data[8], "big")

    def is_resend_request(self):
        return self.data[9] == b"1"

    def get_to(self):
        return int.from_bytes(self.data[0], "big")

    def get_expected_length(self):
        if self.data[7] != b"":
            return int.from_bytes(self.data[7], "big")

    def get_msg(self) -> BasicMultipartMessage:
        m = BasicMultipartMessage()
        m.set_topic("Datagram")
        m.set_subtopic("")
        m.set_val_multiple(self.data)
        return m

    def parse_msg(self, m: BasicMultipartMessage):
        self.data = m.get_multiple_values()

    def get_ids(self) -> tuple[Optional[int], Optional[int]]:
        comm: Optional[bytes | int] = self.data[4]
        packet: Optional[bytes | int] = self.data[5]

        if comm == b"":
            comm = None
        else:
            comm = int.from_bytes(comm, "big")  # type: ignore
        if packet == b"":
            packet = None
        else:
            packet = int.from_bytes(packet, "big")  # type: ignore

        return comm, packet
