# holds structs that go on the Queues to task manager.


from typing import Any

import dill


class Node_Request:
    """Represents requests COMING IN to the node communication manager"""

    def __init__(
        self,
        *,
        routing: dict[str, Any],
        headers: dict[str, Any],
        body: Any,
    ):
        """Create request

        Args:
            routing (dict[str, Any]): Routing dictionary. Is not sent over wire
            headers (dict[str, Any]): Headers. Is sent over wire
            body (Any): Body. Is sent over wire
        """

        self.routing = routing
        self.headers = headers
        self.body = body

    def __str__(self):
        return str(
            {"ROUTING": self.routing, "HEADERS": self.headers, "BODY": self.body}
        )

    def get_zmq_message(self) -> list[bytes]:
        a = dill.dumps(self.routing)
        b = dill.dumps(self.headers)
        c = dill.dumps(self.body)
        return [a, b, c]

    @classmethod
    def extract_multipart(cls, data):
        a = dill.loads(data[0])
        b = dill.loads(data[1])
        c = dill.loads(data[2])
        return cls(routing=a, headers=b, body=c)

    def get_dill_data(self) -> bytes:
        out_data = dill.dumps(
            (self.headers, self.body), fmode=dill.FILE_FMODE, recurse=True
        )
        return out_data

    def get_multipart(self) -> list[bytes]:
        return self.get_zmq_message()


class Node_Response:
    """Represents responses GOING OUT from the node communication manager"""

    def __init__(
        self,
        *,
        routing: dict[str, Any],
        headers: dict[str, Any],
        body: Any,
    ):
        """Create request

        Args:
            routing (dict[str, Any]): Routing dictionary. Is not sent over wire
            headers (dict[str, Any]): Headers. Is sent over wire
            body (Any): Body. Is sent over wire
        """
        self.routing = routing
        self.headers = headers
        self.body = body

    def __str__(self):
        return str(
            {"ROUTING": self.routing, "HEADERS": self.headers, "BODY": self.body}
        )

    @classmethod
    def extract_multipart(cls, data):
        a = dill.loads(data[0])
        b = dill.loads(data[1])
        c = dill.loads(data[2])
        return cls(routing=a, headers=b, body=c)

    def get_zmq_message(self) -> list[bytes]:
        a = dill.dumps(self.routing)
        b = dill.dumps(self.headers)
        c = dill.dumps(self.body)
        return [a, b, c]

    def get_dill_data(self) -> bytes:
        out_data = dill.dumps(
            (self.headers, self.body), fmode=dill.FILE_FMODE, recurse=True
        )
        return out_data

    def get_multipart(self) -> list[bytes]:
        return self.get_zmq_message()
