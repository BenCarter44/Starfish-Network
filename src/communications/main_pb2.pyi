from . import primitives_pb2 as _primitives_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import (
    ClassVar as _ClassVar,
    Iterable as _Iterable,
    Mapping as _Mapping,
    Optional as _Optional,
    Union as _Union,
)

DESCRIPTOR: _descriptor.FileDescriptor

class DHTStatus(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    UNKNOWN: _ClassVar[DHTStatus]
    FOUND: _ClassVar[DHTStatus]
    NOT_FOUND: _ClassVar[DHTStatus]
    OWNED: _ClassVar[DHTStatus]
    OK: _ClassVar[DHTStatus]
    ERR: _ClassVar[DHTStatus]

class DHTSelect(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    BLANK: _ClassVar[DHTSelect]
    PEER_ID: _ClassVar[DHTSelect]
    TASK_ID: _ClassVar[DHTSelect]
    FILE_ID: _ClassVar[DHTSelect]

class MODE(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    NA: _ClassVar[MODE]
    FORWARD: _ClassVar[MODE]
    BACKWARD: _ClassVar[MODE]

UNKNOWN: DHTStatus
FOUND: DHTStatus
NOT_FOUND: DHTStatus
OWNED: DHTStatus
OK: DHTStatus
ERR: DHTStatus
BLANK: DHTSelect
PEER_ID: DHTSelect
TASK_ID: DHTSelect
FILE_ID: DHTSelect
NA: MODE
FORWARD: MODE
BACKWARD: MODE

class DHT_Fetch_Request(_message.Message):
    __slots__ = ("key", "query_chain", "status", "select")
    KEY_FIELD_NUMBER: _ClassVar[int]
    QUERY_CHAIN_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    SELECT_FIELD_NUMBER: _ClassVar[int]
    key: bytes
    query_chain: _containers.RepeatedScalarFieldContainer[bytes]
    status: DHTStatus
    select: DHTSelect
    def __init__(
        self,
        key: _Optional[bytes] = ...,
        query_chain: _Optional[_Iterable[bytes]] = ...,
        status: _Optional[_Union[DHTStatus, str]] = ...,
        select: _Optional[_Union[DHTSelect, str]] = ...,
    ) -> None: ...

class DHT_Fetch_Response(_message.Message):
    __slots__ = ("key", "value", "query_chain", "status", "select")
    KEY_FIELD_NUMBER: _ClassVar[int]
    VALUE_FIELD_NUMBER: _ClassVar[int]
    QUERY_CHAIN_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    SELECT_FIELD_NUMBER: _ClassVar[int]
    key: bytes
    value: bytes
    query_chain: _containers.RepeatedScalarFieldContainer[bytes]
    status: DHTStatus
    select: DHTSelect
    def __init__(
        self,
        key: _Optional[bytes] = ...,
        value: _Optional[bytes] = ...,
        query_chain: _Optional[_Iterable[bytes]] = ...,
        status: _Optional[_Union[DHTStatus, str]] = ...,
        select: _Optional[_Union[DHTSelect, str]] = ...,
    ) -> None: ...

class DHT_Store_Request(_message.Message):
    __slots__ = ("key", "value", "query_chain", "status", "select", "who")
    KEY_FIELD_NUMBER: _ClassVar[int]
    VALUE_FIELD_NUMBER: _ClassVar[int]
    QUERY_CHAIN_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    SELECT_FIELD_NUMBER: _ClassVar[int]
    WHO_FIELD_NUMBER: _ClassVar[int]
    key: bytes
    value: bytes
    query_chain: _containers.RepeatedScalarFieldContainer[bytes]
    status: DHTStatus
    select: DHTSelect
    who: bytes
    def __init__(
        self,
        key: _Optional[bytes] = ...,
        value: _Optional[bytes] = ...,
        query_chain: _Optional[_Iterable[bytes]] = ...,
        status: _Optional[_Union[DHTStatus, str]] = ...,
        select: _Optional[_Union[DHTSelect, str]] = ...,
        who: _Optional[bytes] = ...,
    ) -> None: ...

class DHT_Store_Response(_message.Message):
    __slots__ = ("key", "query_chain", "status", "select", "who")
    KEY_FIELD_NUMBER: _ClassVar[int]
    QUERY_CHAIN_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    SELECT_FIELD_NUMBER: _ClassVar[int]
    WHO_FIELD_NUMBER: _ClassVar[int]
    key: bytes
    query_chain: _containers.RepeatedScalarFieldContainer[bytes]
    status: DHTStatus
    select: DHTSelect
    who: bytes
    def __init__(
        self,
        key: _Optional[bytes] = ...,
        query_chain: _Optional[_Iterable[bytes]] = ...,
        status: _Optional[_Union[DHTStatus, str]] = ...,
        select: _Optional[_Union[DHTSelect, str]] = ...,
        who: _Optional[bytes] = ...,
    ) -> None: ...

class DHT_Delete_Request(_message.Message):
    __slots__ = ("key", "query_chain", "status", "select", "who")
    KEY_FIELD_NUMBER: _ClassVar[int]
    QUERY_CHAIN_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    SELECT_FIELD_NUMBER: _ClassVar[int]
    WHO_FIELD_NUMBER: _ClassVar[int]
    key: bytes
    query_chain: _containers.RepeatedScalarFieldContainer[bytes]
    status: DHTStatus
    select: DHTSelect
    who: bytes
    def __init__(
        self,
        key: _Optional[bytes] = ...,
        query_chain: _Optional[_Iterable[bytes]] = ...,
        status: _Optional[_Union[DHTStatus, str]] = ...,
        select: _Optional[_Union[DHTSelect, str]] = ...,
        who: _Optional[bytes] = ...,
    ) -> None: ...

class DHT_Delete_Response(_message.Message):
    __slots__ = ("status",)
    STATUS_FIELD_NUMBER: _ClassVar[int]
    status: DHTStatus
    def __init__(self, status: _Optional[_Union[DHTStatus, str]] = ...) -> None: ...

class DHT_Delete_Notice_Request(_message.Message):
    __slots__ = ("key", "select", "who")
    KEY_FIELD_NUMBER: _ClassVar[int]
    SELECT_FIELD_NUMBER: _ClassVar[int]
    WHO_FIELD_NUMBER: _ClassVar[int]
    key: bytes
    select: DHTSelect
    who: bytes
    def __init__(
        self,
        key: _Optional[bytes] = ...,
        select: _Optional[_Union[DHTSelect, str]] = ...,
        who: _Optional[bytes] = ...,
    ) -> None: ...

class DHT_Delete_Notice_Response(_message.Message):
    __slots__ = ("status",)
    STATUS_FIELD_NUMBER: _ClassVar[int]
    status: DHTStatus
    def __init__(self, status: _Optional[_Union[DHTStatus, str]] = ...) -> None: ...

class DHT_Update_Request(_message.Message):
    __slots__ = ("key", "value", "select", "who")
    KEY_FIELD_NUMBER: _ClassVar[int]
    VALUE_FIELD_NUMBER: _ClassVar[int]
    SELECT_FIELD_NUMBER: _ClassVar[int]
    WHO_FIELD_NUMBER: _ClassVar[int]
    key: bytes
    value: bytes
    select: DHTSelect
    who: bytes
    def __init__(
        self,
        key: _Optional[bytes] = ...,
        value: _Optional[bytes] = ...,
        select: _Optional[_Union[DHTSelect, str]] = ...,
        who: _Optional[bytes] = ...,
    ) -> None: ...

class DHT_Update_Notice_Request(_message.Message):
    __slots__ = ("key", "value", "select", "who")
    KEY_FIELD_NUMBER: _ClassVar[int]
    VALUE_FIELD_NUMBER: _ClassVar[int]
    SELECT_FIELD_NUMBER: _ClassVar[int]
    WHO_FIELD_NUMBER: _ClassVar[int]
    key: bytes
    value: bytes
    select: DHTSelect
    who: bytes
    def __init__(
        self,
        key: _Optional[bytes] = ...,
        value: _Optional[bytes] = ...,
        select: _Optional[_Union[DHTSelect, str]] = ...,
        who: _Optional[bytes] = ...,
    ) -> None: ...

class DHT_Update_Response(_message.Message):
    __slots__ = ("status",)
    STATUS_FIELD_NUMBER: _ClassVar[int]
    status: DHTStatus
    def __init__(self, status: _Optional[_Union[DHTStatus, str]] = ...) -> None: ...

class DHT_Update_Notice_Response(_message.Message):
    __slots__ = ("status",)
    STATUS_FIELD_NUMBER: _ClassVar[int]
    status: DHTStatus
    def __init__(self, status: _Optional[_Union[DHTStatus, str]] = ...) -> None: ...

class DHT_Register_Notices_Request(_message.Message):
    __slots__ = ("key", "who", "select")
    KEY_FIELD_NUMBER: _ClassVar[int]
    WHO_FIELD_NUMBER: _ClassVar[int]
    SELECT_FIELD_NUMBER: _ClassVar[int]
    key: bytes
    who: bytes
    select: DHTSelect
    def __init__(
        self,
        key: _Optional[bytes] = ...,
        who: _Optional[bytes] = ...,
        select: _Optional[_Union[DHTSelect, str]] = ...,
    ) -> None: ...

class DHT_Register_Notices_Response(_message.Message):
    __slots__ = ("status", "select")
    STATUS_FIELD_NUMBER: _ClassVar[int]
    SELECT_FIELD_NUMBER: _ClassVar[int]
    status: DHTStatus
    select: DHTSelect
    def __init__(
        self,
        status: _Optional[_Union[DHTStatus, str]] = ...,
        select: _Optional[_Union[DHTSelect, str]] = ...,
    ) -> None: ...

class PING(_message.Message):
    __slots__ = ("value",)
    VALUE_FIELD_NUMBER: _ClassVar[int]
    value: int
    def __init__(self, value: _Optional[int] = ...) -> None: ...

class PONG(_message.Message):
    __slots__ = ("value",)
    VALUE_FIELD_NUMBER: _ClassVar[int]
    value: int
    def __init__(self, value: _Optional[int] = ...) -> None: ...

class TaskAllocate_Request(_message.Message):
    __slots__ = ("task",)
    TASK_FIELD_NUMBER: _ClassVar[int]
    task: _primitives_pb2.TaskIdentifier
    def __init__(
        self, task: _Optional[_Union[_primitives_pb2.TaskIdentifier, _Mapping]] = ...
    ) -> None: ...

class TaskAllocate_Response(_message.Message):
    __slots__ = ("status",)
    STATUS_FIELD_NUMBER: _ClassVar[int]
    status: DHTStatus
    def __init__(self, status: _Optional[_Union[DHTStatus, str]] = ...) -> None: ...

class SendEvent_Request(_message.Message):
    __slots__ = ("evt", "who")
    EVT_FIELD_NUMBER: _ClassVar[int]
    WHO_FIELD_NUMBER: _ClassVar[int]
    evt: _primitives_pb2.Event
    who: bytes
    def __init__(
        self,
        evt: _Optional[_Union[_primitives_pb2.Event, _Mapping]] = ...,
        who: _Optional[bytes] = ...,
    ) -> None: ...

class SendEvent_Response(_message.Message):
    __slots__ = ("status", "remaining", "who")
    STATUS_FIELD_NUMBER: _ClassVar[int]
    REMAINING_FIELD_NUMBER: _ClassVar[int]
    WHO_FIELD_NUMBER: _ClassVar[int]
    status: DHTStatus
    remaining: int
    who: bytes
    def __init__(
        self,
        status: _Optional[_Union[DHTStatus, str]] = ...,
        remaining: _Optional[int] = ...,
        who: _Optional[bytes] = ...,
    ) -> None: ...

class Bootstrap_Request(_message.Message):
    __slots__ = ("peerID", "dial_from")
    PEERID_FIELD_NUMBER: _ClassVar[int]
    DIAL_FROM_FIELD_NUMBER: _ClassVar[int]
    peerID: bytes
    dial_from: _primitives_pb2.TransportAddress
    def __init__(
        self,
        peerID: _Optional[bytes] = ...,
        dial_from: _Optional[_Union[_primitives_pb2.TransportAddress, _Mapping]] = ...,
    ) -> None: ...

class Bootstrap_Response(_message.Message):
    __slots__ = ("value",)
    VALUE_FIELD_NUMBER: _ClassVar[int]
    value: _containers.RepeatedCompositeFieldContainer[Bootstrap_Item]
    def __init__(
        self, value: _Optional[_Iterable[_Union[Bootstrap_Item, _Mapping]]] = ...
    ) -> None: ...

class Bootstrap_Item(_message.Message):
    __slots__ = ("peer_id", "addr")
    PEER_ID_FIELD_NUMBER: _ClassVar[int]
    ADDR_FIELD_NUMBER: _ClassVar[int]
    peer_id: bytes
    addr: _primitives_pb2.TransportAddress
    def __init__(
        self,
        peer_id: _Optional[bytes] = ...,
        addr: _Optional[_Union[_primitives_pb2.TransportAddress, _Mapping]] = ...,
    ) -> None: ...

class Heartbeat_Request(_message.Message):
    __slots__ = ("custom_data",)
    CUSTOM_DATA_FIELD_NUMBER: _ClassVar[int]
    custom_data: bytes
    def __init__(self, custom_data: _Optional[bytes] = ...) -> None: ...

class Heartbeat_Response(_message.Message):
    __slots__ = ("custom_data",)
    CUSTOM_DATA_FIELD_NUMBER: _ClassVar[int]
    custom_data: bytes
    def __init__(self, custom_data: _Optional[bytes] = ...) -> None: ...

class SendMonitor_Request(_message.Message):
    __slots__ = ("process_data", "who", "task")
    PROCESS_DATA_FIELD_NUMBER: _ClassVar[int]
    WHO_FIELD_NUMBER: _ClassVar[int]
    TASK_FIELD_NUMBER: _ClassVar[int]
    process_data: bytes
    who: bytes
    task: _primitives_pb2.TaskIdentifier
    def __init__(
        self,
        process_data: _Optional[bytes] = ...,
        who: _Optional[bytes] = ...,
        task: _Optional[_Union[_primitives_pb2.TaskIdentifier, _Mapping]] = ...,
    ) -> None: ...

class SendMonitor_Response(_message.Message):
    __slots__ = ("status",)
    STATUS_FIELD_NUMBER: _ClassVar[int]
    status: DHTStatus
    def __init__(self, status: _Optional[_Union[DHTStatus, str]] = ...) -> None: ...

class SendCheckpoint_Request(_message.Message):
    __slots__ = ("process_data", "who", "event_origin", "event_to", "mode")
    PROCESS_DATA_FIELD_NUMBER: _ClassVar[int]
    WHO_FIELD_NUMBER: _ClassVar[int]
    EVENT_ORIGIN_FIELD_NUMBER: _ClassVar[int]
    EVENT_TO_FIELD_NUMBER: _ClassVar[int]
    MODE_FIELD_NUMBER: _ClassVar[int]
    process_data: bytes
    who: bytes
    event_origin: bytes
    event_to: bytes
    mode: MODE
    def __init__(
        self,
        process_data: _Optional[bytes] = ...,
        who: _Optional[bytes] = ...,
        event_origin: _Optional[bytes] = ...,
        event_to: _Optional[bytes] = ...,
        mode: _Optional[_Union[MODE, str]] = ...,
    ) -> None: ...

class SendCheckpoint_Response(_message.Message):
    __slots__ = ("status",)
    STATUS_FIELD_NUMBER: _ClassVar[int]
    status: DHTStatus
    def __init__(self, status: _Optional[_Union[DHTStatus, str]] = ...) -> None: ...
