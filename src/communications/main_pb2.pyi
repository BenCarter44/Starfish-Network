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

class DHTSelect(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    BLANK: _ClassVar[DHTSelect]
    PEER_ID: _ClassVar[DHTSelect]
    TASK_ID: _ClassVar[DHTSelect]
    FILE_ID: _ClassVar[DHTSelect]

UNKNOWN: DHTStatus
FOUND: DHTStatus
NOT_FOUND: DHTStatus
OWNED: DHTStatus
BLANK: DHTSelect
PEER_ID: DHTSelect
TASK_ID: DHTSelect
FILE_ID: DHTSelect

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

class DHT_Store_Response(_message.Message):
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
    __slots__ = ("evt",)
    EVT_FIELD_NUMBER: _ClassVar[int]
    evt: _primitives_pb2.Event
    def __init__(
        self, evt: _Optional[_Union[_primitives_pb2.Event, _Mapping]] = ...
    ) -> None: ...

class SendEvent_Response(_message.Message):
    __slots__ = ("status",)
    STATUS_FIELD_NUMBER: _ClassVar[int]
    status: DHTStatus
    def __init__(self, status: _Optional[_Union[DHTStatus, str]] = ...) -> None: ...

class SearchPeer_Request(_message.Message):
    __slots__ = ("peer",)
    PEER_FIELD_NUMBER: _ClassVar[int]
    peer: bytes
    def __init__(self, peer: _Optional[bytes] = ...) -> None: ...

class SearchPeer_Response(_message.Message):
    __slots__ = ("addr", "status")
    ADDR_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    addr: _primitives_pb2.TransportAddress
    status: DHTStatus
    def __init__(
        self,
        addr: _Optional[_Union[_primitives_pb2.TransportAddress, _Mapping]] = ...,
        status: _Optional[_Union[DHTStatus, str]] = ...,
    ) -> None: ...

class StorePeer_Request(_message.Message):
    __slots__ = ("peer", "addr")
    PEER_FIELD_NUMBER: _ClassVar[int]
    ADDR_FIELD_NUMBER: _ClassVar[int]
    peer: bytes
    addr: _primitives_pb2.TransportAddress
    def __init__(
        self,
        peer: _Optional[bytes] = ...,
        addr: _Optional[_Union[_primitives_pb2.TransportAddress, _Mapping]] = ...,
    ) -> None: ...

class StorePeer_Response(_message.Message):
    __slots__ = ("code",)
    CODE_FIELD_NUMBER: _ClassVar[int]
    code: int
    def __init__(self, code: _Optional[int] = ...) -> None: ...

class BOOTSTRAP(_message.Message):
    __slots__ = ("dial_to",)
    FROM_FIELD_NUMBER: _ClassVar[int]
    DIAL_TO_FIELD_NUMBER: _ClassVar[int]
    dial_to: _primitives_pb2.TransportAddress
    def __init__(
        self,
        dial_to: _Optional[_Union[_primitives_pb2.TransportAddress, _Mapping]] = ...,
        **kwargs
    ) -> None: ...
