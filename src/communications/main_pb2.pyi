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

class FILE_TYPE(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    FILE: _ClassVar[FILE_TYPE]
    IO: _ClassVar[FILE_TYPE]
    DIR: _ClassVar[FILE_TYPE]
    CHUNK: _ClassVar[FILE_TYPE]

class FILE_REQUEST(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    READ: _ClassVar[FILE_REQUEST]
    WRITE: _ClassVar[FILE_REQUEST]
    SEEK: _ClassVar[FILE_REQUEST]
    CREATE: _ClassVar[FILE_REQUEST]
    CLOSE: _ClassVar[FILE_REQUEST]
    OPEN: _ClassVar[FILE_REQUEST]
    TELL: _ClassVar[FILE_REQUEST]

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
FILE: FILE_TYPE
IO: FILE_TYPE
DIR: FILE_TYPE
CHUNK: FILE_TYPE
READ: FILE_REQUEST
WRITE: FILE_REQUEST
SEEK: FILE_REQUEST
CREATE: FILE_REQUEST
CLOSE: FILE_REQUEST
OPEN: FILE_REQUEST
TELL: FILE_REQUEST

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

class FileGeneric(_message.Message):
    __slots__ = ("type", "contents", "date_created")
    TYPE_FIELD_NUMBER: _ClassVar[int]
    CONTENTS_FIELD_NUMBER: _ClassVar[int]
    DATE_CREATED_FIELD_NUMBER: _ClassVar[int]
    type: FILE_TYPE
    contents: bytes
    date_created: bytes
    def __init__(
        self,
        type: _Optional[_Union[FILE_TYPE, str]] = ...,
        contents: _Optional[bytes] = ...,
        date_created: _Optional[bytes] = ...,
    ) -> None: ...

class FileValue(_message.Message):
    __slots__ = ("peerID", "identifier")
    PEERID_FIELD_NUMBER: _ClassVar[int]
    IDENTIFIER_FIELD_NUMBER: _ClassVar[int]
    peerID: bytes
    identifier: bytes
    def __init__(
        self, peerID: _Optional[bytes] = ..., identifier: _Optional[bytes] = ...
    ) -> None: ...

class File(_message.Message):
    __slots__ = ("length", "data")
    LENGTH_FIELD_NUMBER: _ClassVar[int]
    DATA_FIELD_NUMBER: _ClassVar[int]
    length: int
    data: bytes
    def __init__(
        self, length: _Optional[int] = ..., data: _Optional[bytes] = ...
    ) -> None: ...

class IOContainer(_message.Message):
    __slots__ = ("peerID", "ioKey")
    PEERID_FIELD_NUMBER: _ClassVar[int]
    IOKEY_FIELD_NUMBER: _ClassVar[int]
    peerID: bytes
    ioKey: bytes
    def __init__(
        self, peerID: _Optional[bytes] = ..., ioKey: _Optional[bytes] = ...
    ) -> None: ...

class Directory(_message.Message):
    __slots__ = ("number_of_files", "file_list")
    NUMBER_OF_FILES_FIELD_NUMBER: _ClassVar[int]
    FILE_LIST_FIELD_NUMBER: _ClassVar[int]
    number_of_files: int
    file_list: _containers.RepeatedScalarFieldContainer[bytes]
    def __init__(
        self,
        number_of_files: _Optional[int] = ...,
        file_list: _Optional[_Iterable[bytes]] = ...,
    ) -> None: ...

class FileServiceRequest(_message.Message):
    __slots__ = ("local_file_identifier", "key", "file_request", "data", "process_id")
    LOCAL_FILE_IDENTIFIER_FIELD_NUMBER: _ClassVar[int]
    KEY_FIELD_NUMBER: _ClassVar[int]
    FILE_REQUEST_FIELD_NUMBER: _ClassVar[int]
    DATA_FIELD_NUMBER: _ClassVar[int]
    PROCESS_ID_FIELD_NUMBER: _ClassVar[int]
    local_file_identifier: bytes
    key: bytes
    file_request: FILE_REQUEST
    data: bytes
    process_id: bytes
    def __init__(
        self,
        local_file_identifier: _Optional[bytes] = ...,
        key: _Optional[bytes] = ...,
        file_request: _Optional[_Union[FILE_REQUEST, str]] = ...,
        data: _Optional[bytes] = ...,
        process_id: _Optional[bytes] = ...,
    ) -> None: ...

class FileServiceResponse(_message.Message):
    __slots__ = ("status", "data")
    STATUS_FIELD_NUMBER: _ClassVar[int]
    DATA_FIELD_NUMBER: _ClassVar[int]
    status: DHTStatus
    data: bytes
    def __init__(
        self,
        status: _Optional[_Union[DHTStatus, str]] = ...,
        data: _Optional[bytes] = ...,
    ) -> None: ...
