from typing import List, Tuple

from src.ttl import DataTTL
from src.utils import dump


class BasicMultipartMessage:
    """The parent class of all messages"""

    def __init__(self):
        """Init a basic bare message"""
        self.output: list[bytes] = [b"dummy", b""]

    def set_val(self, val: bytes):
        """Set value of message

        Args:
            val (bytes): Value
        """
        self.output[1] = val

    def get_val(self) -> bytes:
        """Get value of message

        Returns:
            bytes: The value of the message
        """
        return self.output[1]

    def compile(self) -> list[bytes]:
        """Get raw multipart message

        Returns:
            list[bytes]: Multipart message
        """
        return self.output

    def import_msg(self, data_in: list[bytes]):
        """Import multipart message

        Args:
            data_in (list[bytes]): multipart message
        """
        self.output = data_in

    def compile_with_address(self, addr: bytes) -> list[bytes]:
        """Return multipart message with address

        Args:
            addr (bytes): Address to add to message

        Returns:
            List[bytes]: multipart message
        """
        d = self.compile()
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
        self.output = [b""]
        self.output[0] = b"General"

    def fetch_state_command(self, r_identity: int):
        """Create a fetch-state message

        Args:
            r_identity (int): Reply identity
        """
        self.output = [b"", b"", b""]
        self.output[0] = b"General"
        self.output[1] = b"fetch_state"
        self.output[2] = int.to_bytes(r_identity, 2, "big")

    def is_fetch_state(self) -> bool:
        """See if message is a fetch-state message

        Returns:
            bool: True if fetch-state message
        """
        return self.output[1] == b"fetch_state"

    def is_return_state(self) -> bool:
        """See if message is a return-state message

        Returns:
            bool: True if return-state message
        """
        return self.output[1] == b"return_state"

    def is_push_change(self) -> bool:
        """See if message is a push-change message

        Returns:
            bool: True if a push-change message
        """
        return self.output[1] == b"push_change"

    def is_push_change_receive(self) -> bool:
        """See if message is a push-change-receive message

        Returns:
            bool: True if a push-change-receive message
        """
        return self.output[1] == b"push_change_receive"

    def is_requesting_connection(self) -> bool:
        """See if message is a requesting-connection message

        Returns:
            bool: True if a requesting-connection message
        """
        return self.output[1] == b"request_connection"

    def is_requesting_connection_feedback(self) -> bool:
        """See if message is a request-connection-feedback message

        Returns:
            bool: True if message is a request-connection-feedback message
        """
        return self.output[1] == b"request_connection_ok"

    def is_requesting_disconnection(self) -> bool:
        """See if message is a request-disconnection message

        Returns:
            bool: True if message is a request-disconnection message
        """
        return self.output[1] == b"request_disconnection"

    def request_disconnect(self, r_identity: int):
        """Create request-disconnect message

        Args:
            r_identity (int): Reply identity
        """
        self.output = [b"", b"", b""]
        self.output[0] = b"General"
        self.output[1] = b"request_disconnection"
        self.output[2] = int.to_bytes(r_identity, 2, "big")

    def request_connection_cmd(self, r_identity: int):
        """Create request-connection message

        Args:
            r_identity (int): Reply identity
        """
        self.output = [b"", b"", b""]
        self.output[0] = b"General"
        self.output[1] = b"request_connection"
        self.output[2] = int.to_bytes(r_identity, 2, "big")

    def request_connection_feedback(self, r_identity: int):
        """Create request-connection-feedback message

        Args:
            r_identity (int): Reply identity
        """
        self.output = [b"", b"", b""]
        self.output[0] = b"General"
        self.output[1] = b"request_connection_ok"
        self.output[2] = int.to_bytes(r_identity, 2, "big")

    def return_state_receipt(self, values: List[Tuple[str, DataTTL]], r_identity: int):
        """Create state-return message

        Args:
            values (List[Tuple[str, DataWithTTL]]): Keys with values - keyvalue store
            r_identity (int): Reply identity
        """
        self.output = [b"", b"", b"", b""]
        self.output[0] = b"General"
        self.output[1] = b"return_state"
        self.output[2] = int.to_bytes(r_identity, 2, "big")
        self.output[3] = int.to_bytes(len(values), 4, "big")
        for x in values:
            self.output.append(x[0].encode("utf-8"))
            self.output.append(x[1].to_bytes())

    def push_change(self, key: str, value: DataTTL, r_identity: int):
        """Push single change message

        Args:
            key (str): key
            value (DataWithTTL): value with ttl management
            r_identity (int): Reply identity
        """
        self.output = [b"", b"", b"", b"", b"", b""]
        self.output[0] = b"General"
        self.output[1] = b"push_change"
        self.output[2] = int.to_bytes(r_identity, 2, "big")
        self.output[3] = int.to_bytes(1, 4, "big")
        self.output[4] = key.encode("utf-8")
        self.output[5] = value.to_bytes()

    def get_push_key_val(self) -> tuple[str, DataTTL]:
        """Get key value from message

        Returns:
            str: key
            DataWithTTL: value
        """
        dt = DataTTL(None, 0, True)
        dt.from_bytes(self.output[5])
        return self.output[4].decode("utf-8"), dt

    def return_push_change(self, r_identity: int):
        """Create return-push-change

        Args:
            r_identity (int): Reply identity
        """
        self.output = [b"", b"", b""]
        self.output[0] = b"General"
        self.output[1] = b"push_change_receive"
        self.output[2] = int.to_bytes(r_identity, 2, "big")

    def get_state_from_return(self) -> List[Tuple[str, DataTTL]]:
        """Load state from message

        Returns:
            List[Tuple[str, DataWithTTL]]: keyvalue state
        """
        assert self.output[1] == b"return_state"
        length = int.from_bytes(self.output[3], "big")

        out: list[tuple[str, DataTTL]] = list(range(length))  # type: ignore
        # assumes length is not lying, telling the truth
        state_data = self.output[4:]
        for x in range(length):
            dt = DataTTL(None, 0, True)
            dt.from_bytes(state_data[x * 2 + 1])
            out[x] = (state_data[x * 2].decode("utf-8"), dt)
        return out

    def import_msg(self, data_in: list[bytes]):
        """Import message and check if valid

        Args:
            data_in (list[bytes]): Imported Message

        Raises:
            ValueError: Malformed message
        """
        self.output = data_in
        if self.output[0] != b"General" and len(self.output) < 3:
            raise ValueError("Malformed Peer KV General Message!")

    def get_r_identity(self) -> int:
        """Get Reply Identity from message

        Returns:
            int: Reply identity
        """
        return int.from_bytes(self.output[2], "big")

    def is_error_msg(self) -> bool:
        """See if error message

        Returns:
            bool: True if error message
        """
        return self.output[1] == b"Error"

    def get_error_code(self) -> tuple[int, str]:
        """Get error code and value

        Returns:
            tuple[int, str]: error number and value
        """
        return int.from_bytes(self.output[3], "big"), self.output[4].decode("utf-8")

    def error_feedback(self, code: int, cmd: str, r_identity: int):
        """Create error message

        Args:
            code (int): Error code
            cmd (str): Error value
            r_identity (int): Reply Identity
        """
        self.output = [b"", b"", b"", b"", b""]
        self.output[0] = b"General"
        self.output[1] = b"Error"
        self.output[2] = int.to_bytes(r_identity, 2, "big")
        self.output[3] = int.to_bytes(code, 2, "big")
        self.output[4] = cmd.encode("utf-8")


class PeerKV_Hello(PeerKV):
    """Hello sequence of messages

    Inherits:
        PeerKV
    """

    def __init__(self):
        """Setup object"""
        super(PeerKV_Hello, self).__init__()
        self.output = [b"", b"", b"", b"", b"", b""]

    def create(self, r_check: int, serving_endpoint_query: str):
        """Create hello message

        Args:
            r_check (int): Reply Identity
            serving_endpoint_query (str): Endpoint
        """
        self.output[0] = b"Hello!"
        self.output[1] = b"key_update"
        self.output[2] = int.to_bytes(r_check, 2, "big")
        self.output[3] = int.to_bytes(2, 4, "big")
        self.output[4] = "blank".encode("utf-8")
        self.output[5] = serving_endpoint_query.encode("utf-8")

    def create_welcome(self, r_check: int):
        """Create welcome message

        Args:
            r_check (int): Endpoint
        """
        self.output = [b"", b"", b""]
        self.output[0] = b"Welcome"
        self.output[1] = b"pizza!"
        self.output[2] = int.to_bytes(r_check, 2, "big")

    def set_welcome(self):
        """Set welcome message"""
        self.output[0] = b"Welcome"

    def import_msg(self, data_in: list[bytes]):
        """Import multipart message, check if valid Hello message

        Args:
            data_in (list[bytes]): Multipart message

        Raises:
            ValueError: Malformed message
        """
        self.output = data_in

        if (self.output[0] != b"Hello" or self.output[0] != b"Welcome") and len(
            self.output
        ) % 3 != 0:

            raise ValueError("Malformed Peer KV Hello Message!")

    def get_endpoint(self) -> str:
        """Get hello endpoint

        Returns:
            str: endpoint
        """
        return self.output[5].decode("utf-8")
