from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class TaskIdentifier(_message.Message):
    __slots__ = ("user_id", "process_id", "task_id", "callable_data", "pass_id")
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    PROCESS_ID_FIELD_NUMBER: _ClassVar[int]
    TASK_ID_FIELD_NUMBER: _ClassVar[int]
    CALLABLE_DATA_FIELD_NUMBER: _ClassVar[int]
    PASS_ID_FIELD_NUMBER: _ClassVar[int]
    user_id: bytes
    process_id: bytes
    task_id: bytes
    callable_data: bytes
    pass_id: int
    def __init__(self, user_id: _Optional[bytes] = ..., process_id: _Optional[bytes] = ..., task_id: _Optional[bytes] = ..., callable_data: _Optional[bytes] = ..., pass_id: _Optional[int] = ...) -> None: ...

class TaskValue(_message.Message):
    __slots__ = ("address", "task_data")
    ADDRESS_FIELD_NUMBER: _ClassVar[int]
    TASK_DATA_FIELD_NUMBER: _ClassVar[int]
    address: bytes
    task_data: bytes
    def __init__(self, address: _Optional[bytes] = ..., task_data: _Optional[bytes] = ...) -> None: ...

class Process(_message.Message):
    __slots__ = ("user", "process_id")
    USER_FIELD_NUMBER: _ClassVar[int]
    PROCESS_ID_FIELD_NUMBER: _ClassVar[int]
    user: bytes
    process_id: bytes
    def __init__(self, user: _Optional[bytes] = ..., process_id: _Optional[bytes] = ...) -> None: ...

class TransportAddress(_message.Message):
    __slots__ = ("protocol", "host", "port")
    PROTOCOL_FIELD_NUMBER: _ClassVar[int]
    HOST_FIELD_NUMBER: _ClassVar[int]
    PORT_FIELD_NUMBER: _ClassVar[int]
    protocol: bytes
    host: bytes
    port: bytes
    def __init__(self, protocol: _Optional[bytes] = ..., host: _Optional[bytes] = ..., port: _Optional[bytes] = ...) -> None: ...

class Event(_message.Message):
    __slots__ = ("task_to", "data", "system_data")
    TASK_TO_FIELD_NUMBER: _ClassVar[int]
    DATA_FIELD_NUMBER: _ClassVar[int]
    SYSTEM_DATA_FIELD_NUMBER: _ClassVar[int]
    task_to: TaskIdentifier
    data: bytes
    system_data: bytes
    def __init__(self, task_to: _Optional[_Union[TaskIdentifier, _Mapping]] = ..., data: _Optional[bytes] = ..., system_data: _Optional[bytes] = ...) -> None: ...
