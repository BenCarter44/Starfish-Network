# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# NO CHECKED-IN PROTOBUF GENCODE
# source: primitives.proto
# Protobuf Python Version: 5.28.1
"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import runtime_version as _runtime_version
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder
_runtime_version.ValidateProtobufRuntimeVersion(
    _runtime_version.Domain.PUBLIC,
    5,
    28,
    1,
    '',
    'primitives.proto'
)
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()




DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\x10primitives.proto\x12\x08protocol\"n\n\x0eTaskIdentifier\x12\x0f\n\x07user_id\x18\x01 \x01(\x0c\x12\x12\n\nprocess_id\x18\x02 \x01(\x0c\x12\x0f\n\x07task_id\x18\x03 \x01(\x0c\x12\x15\n\rcallable_data\x18\x04 \x01(\x0c\x12\x0f\n\x07pass_id\x18\x05 \x01(\x05\"/\n\tTaskValue\x12\x0f\n\x07\x61\x64\x64ress\x18\x01 \x01(\x0c\x12\x11\n\ttask_data\x18\x02 \x01(\x0c\"+\n\x07Process\x12\x0c\n\x04user\x18\x01 \x01(\x0c\x12\x12\n\nprocess_id\x18\x02 \x01(\x0c\"@\n\x10TransportAddress\x12\x10\n\x08protocol\x18\x01 \x01(\x0c\x12\x0c\n\x04host\x18\x02 \x01(\x0c\x12\x0c\n\x04port\x18\x03 \x01(\x0c\"U\n\x05\x45vent\x12)\n\x07task_to\x18\x01 \x01(\x0b\x32\x18.protocol.TaskIdentifier\x12\x0c\n\x04\x64\x61ta\x18\x02 \x01(\x0c\x12\x13\n\x0bsystem_data\x18\x03 \x01(\x0c\x62\x06proto3')

_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'primitives_pb2', _globals)
if not _descriptor._USE_C_DESCRIPTORS:
  DESCRIPTOR._loaded_options = None
  _globals['_TASKIDENTIFIER']._serialized_start=30
  _globals['_TASKIDENTIFIER']._serialized_end=140
  _globals['_TASKVALUE']._serialized_start=142
  _globals['_TASKVALUE']._serialized_end=189
  _globals['_PROCESS']._serialized_start=191
  _globals['_PROCESS']._serialized_end=234
  _globals['_TRANSPORTADDRESS']._serialized_start=236
  _globals['_TRANSPORTADDRESS']._serialized_end=300
  _globals['_EVENT']._serialized_start=302
  _globals['_EVENT']._serialized_end=387
# @@protoc_insertion_point(module_scope)