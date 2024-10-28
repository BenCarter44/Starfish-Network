# holds structs that go on the Queues to task manager.


from typing import Any


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
