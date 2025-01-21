# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# NO CHECKED-IN PROTOBUF GENCODE
# source: main.proto
# Protobuf Python Version: 5.28.1
"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import runtime_version as _runtime_version
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder

_runtime_version.ValidateProtobufRuntimeVersion(
    _runtime_version.Domain.PUBLIC, 5, 28, 1, "", "main.proto"
)
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


from . import primitives_pb2 as primitives__pb2


DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(
    b'\n\nmain.proto\x12\x08protocol\x1a\x10primitives.proto"\x7f\n\x11\x44HT_Fetch_Request\x12\x0b\n\x03key\x18\x01 \x01(\x0c\x12\x13\n\x0bquery_chain\x18\x02 \x03(\x0c\x12#\n\x06status\x18\x03 \x01(\x0e\x32\x13.protocol.DHTStatus\x12#\n\x06select\x18\x04 \x01(\x0e\x32\x13.protocol.DHTSelect"\x8f\x01\n\x12\x44HT_Fetch_Response\x12\x0b\n\x03key\x18\x01 \x01(\x0c\x12\r\n\x05value\x18\x02 \x01(\x0c\x12\x13\n\x0bquery_chain\x18\x03 \x03(\x0c\x12#\n\x06status\x18\x04 \x01(\x0e\x32\x13.protocol.DHTStatus\x12#\n\x06select\x18\x05 \x01(\x0e\x32\x13.protocol.DHTSelect"\x9b\x01\n\x11\x44HT_Store_Request\x12\x0b\n\x03key\x18\x01 \x01(\x0c\x12\r\n\x05value\x18\x02 \x01(\x0c\x12\x13\n\x0bquery_chain\x18\x03 \x03(\x0c\x12#\n\x06status\x18\x04 \x01(\x0e\x32\x13.protocol.DHTStatus\x12#\n\x06select\x18\x05 \x01(\x0e\x32\x13.protocol.DHTSelect\x12\x0b\n\x03who\x18\x06 \x01(\x0c"\x8d\x01\n\x12\x44HT_Store_Response\x12\x0b\n\x03key\x18\x01 \x01(\x0c\x12\x13\n\x0bquery_chain\x18\x02 \x03(\x0c\x12#\n\x06status\x18\x03 \x01(\x0e\x32\x13.protocol.DHTStatus\x12#\n\x06select\x18\x04 \x01(\x0e\x32\x13.protocol.DHTSelect\x12\x0b\n\x03who\x18\x05 \x01(\x0c"\x8d\x01\n\x12\x44HT_Delete_Request\x12\x0b\n\x03key\x18\x01 \x01(\x0c\x12\x13\n\x0bquery_chain\x18\x02 \x03(\x0c\x12#\n\x06status\x18\x03 \x01(\x0e\x32\x13.protocol.DHTStatus\x12#\n\x06select\x18\x04 \x01(\x0e\x32\x13.protocol.DHTSelect\x12\x0b\n\x03who\x18\x05 \x01(\x0c":\n\x13\x44HT_Delete_Response\x12#\n\x06status\x18\x03 \x01(\x0e\x32\x13.protocol.DHTStatus"Z\n\x19\x44HT_Delete_Notice_Request\x12\x0b\n\x03key\x18\x01 \x01(\x0c\x12#\n\x06select\x18\x04 \x01(\x0e\x32\x13.protocol.DHTSelect\x12\x0b\n\x03who\x18\x05 \x01(\x0c"A\n\x1a\x44HT_Delete_Notice_Response\x12#\n\x06status\x18\x03 \x01(\x0e\x32\x13.protocol.DHTStatus"b\n\x12\x44HT_Update_Request\x12\x0b\n\x03key\x18\x01 \x01(\x0c\x12\r\n\x05value\x18\x02 \x01(\x0c\x12#\n\x06select\x18\x04 \x01(\x0e\x32\x13.protocol.DHTSelect\x12\x0b\n\x03who\x18\x05 \x01(\x0c"i\n\x19\x44HT_Update_Notice_Request\x12\x0b\n\x03key\x18\x01 \x01(\x0c\x12\r\n\x05value\x18\x02 \x01(\x0c\x12#\n\x06select\x18\x04 \x01(\x0e\x32\x13.protocol.DHTSelect\x12\x0b\n\x03who\x18\x05 \x01(\x0c":\n\x13\x44HT_Update_Response\x12#\n\x06status\x18\x03 \x01(\x0e\x32\x13.protocol.DHTStatus"A\n\x1a\x44HT_Update_Notice_Response\x12#\n\x06status\x18\x03 \x01(\x0e\x32\x13.protocol.DHTStatus"]\n\x1c\x44HT_Register_Notices_Request\x12\x0b\n\x03key\x18\x01 \x01(\x0c\x12\x0b\n\x03who\x18\x02 \x01(\x0c\x12#\n\x06select\x18\x03 \x01(\x0e\x32\x13.protocol.DHTSelect"i\n\x1d\x44HT_Register_Notices_Response\x12#\n\x06status\x18\x03 \x01(\x0e\x32\x13.protocol.DHTStatus\x12#\n\x06select\x18\x04 \x01(\x0e\x32\x13.protocol.DHTSelect"\x15\n\x04PING\x12\r\n\x05value\x18\x01 \x01(\x05"\x15\n\x04PONG\x12\r\n\x05value\x18\x01 \x01(\x05">\n\x14TaskAllocate_Request\x12&\n\x04task\x18\x01 \x01(\x0b\x32\x18.protocol.TaskIdentifier"<\n\x15TaskAllocate_Response\x12#\n\x06status\x18\x01 \x01(\x0e\x32\x13.protocol.DHTStatus">\n\x11SendEvent_Request\x12\x1c\n\x03\x65vt\x18\x01 \x01(\x0b\x32\x0f.protocol.Event\x12\x0b\n\x03who\x18\x02 \x01(\x0c"Y\n\x12SendEvent_Response\x12#\n\x06status\x18\x01 \x01(\x0e\x32\x13.protocol.DHTStatus\x12\x11\n\tremaining\x18\x02 \x01(\x05\x12\x0b\n\x03who\x18\x03 \x01(\x0c"R\n\x11\x42ootstrap_Request\x12\x0e\n\x06peerID\x18\x01 \x01(\x0c\x12-\n\tdial_from\x18\x02 \x01(\x0b\x32\x1a.protocol.TransportAddress"=\n\x12\x42ootstrap_Response\x12\'\n\x05value\x18\x01 \x03(\x0b\x32\x18.protocol.Bootstrap_Item"K\n\x0e\x42ootstrap_Item\x12\x0f\n\x07peer_id\x18\x01 \x01(\x0c\x12(\n\x04\x61\x64\x64r\x18\x02 \x01(\x0b\x32\x1a.protocol.TransportAddress"(\n\x11Heartbeat_Request\x12\x13\n\x0b\x63ustom_data\x18\x01 \x01(\x0c")\n\x12Heartbeat_Response\x12\x13\n\x0b\x63ustom_data\x18\x01 \x01(\x0c"`\n\x13SendMonitor_Request\x12\x14\n\x0cprocess_data\x18\x01 \x01(\x0c\x12\x0b\n\x03who\x18\x02 \x01(\x0c\x12&\n\x04task\x18\x03 \x01(\x0b\x32\x18.protocol.TaskIdentifier";\n\x14SendMonitor_Response\x12#\n\x06status\x18\x01 \x01(\x0e\x32\x13.protocol.DHTStatus"c\n\x16SendCheckpoint_Request\x12\x14\n\x0cprocess_data\x18\x01 \x01(\x0c\x12\x0b\n\x03who\x18\x02 \x01(\x0c\x12\x14\n\x0c\x65vent_origin\x18\x03 \x01(\x0c\x12\x10\n\x08\x65vent_to\x18\x04 \x01(\x0c">\n\x17SendCheckpoint_Response\x12#\n\x06status\x18\x01 \x01(\x0e\x32\x13.protocol.DHTStatus*N\n\tDHTStatus\x12\x0b\n\x07UNKNOWN\x10\x00\x12\t\n\x05\x46OUND\x10\x01\x12\r\n\tNOT_FOUND\x10\x02\x12\t\n\x05OWNED\x10\x03\x12\x06\n\x02OK\x10\x04\x12\x07\n\x03\x45RR\x10\x05*=\n\tDHTSelect\x12\t\n\x05\x42LANK\x10\x00\x12\x0b\n\x07PEER_ID\x10\x01\x12\x0b\n\x07TASK_ID\x10\x02\x12\x0b\n\x07\x46ILE_ID\x10\x03\x32\xd4\x04\n\nDHTService\x12H\n\tFetchItem\x12\x1b.protocol.DHT_Fetch_Request\x1a\x1c.protocol.DHT_Fetch_Response"\x00\x12H\n\tStoreItem\x12\x1b.protocol.DHT_Store_Request\x1a\x1c.protocol.DHT_Store_Response"\x00\x12K\n\nDeleteItem\x12\x1c.protocol.DHT_Delete_Request\x1a\x1d.protocol.DHT_Delete_Response"\x00\x12U\n\rDeletedNotice\x12#.protocol.DHT_Delete_Notice_Request\x1a\x1d.protocol.DHT_Delete_Response"\x00\x12K\n\nUpdateItem\x12\x1c.protocol.DHT_Update_Request\x1a\x1d.protocol.DHT_Update_Response"\x00\x12\\\n\rUpdatedNotice\x12#.protocol.DHT_Update_Notice_Request\x1a$.protocol.DHT_Update_Notice_Response"\x00\x12\x63\n\x0eRegisterNotice\x12&.protocol.DHT_Register_Notices_Request\x1a\'.protocol.DHT_Register_Notices_Response"\x00\x32\x87\x02\n\x0bTaskService\x12H\n\tSendEvent\x12\x1b.protocol.SendEvent_Request\x1a\x1c.protocol.SendEvent_Response"\x00\x12U\n\x12SendMonitorRequest\x12\x1d.protocol.SendMonitor_Request\x1a\x1e.protocol.SendMonitor_Response"\x00\x12W\n\x0eSendCheckpoint\x12 .protocol.SendCheckpoint_Request\x1a!.protocol.SendCheckpoint_Response"\x00\x32W\n\x0bPeerService\x12H\n\tBootstrap\x12\x1b.protocol.Bootstrap_Request\x1a\x1c.protocol.Bootstrap_Response"\x00\x32\x8e\x01\n\x10KeepAliveService\x12,\n\x08SendPing\x12\x0e.protocol.PING\x1a\x0e.protocol.PONG"\x00\x12L\n\rSendHeartbeat\x12\x1b.protocol.Heartbeat_Request\x1a\x1c.protocol.Heartbeat_Response"\x00\x62\x06proto3'
)

_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, "main_pb2", _globals)
if not _descriptor._USE_C_DESCRIPTORS:
    DESCRIPTOR._loaded_options = None
    _globals["_DHTSTATUS"]._serialized_start = 2478
    _globals["_DHTSTATUS"]._serialized_end = 2556
    _globals["_DHTSELECT"]._serialized_start = 2558
    _globals["_DHTSELECT"]._serialized_end = 2619
    _globals["_DHT_FETCH_REQUEST"]._serialized_start = 42
    _globals["_DHT_FETCH_REQUEST"]._serialized_end = 169
    _globals["_DHT_FETCH_RESPONSE"]._serialized_start = 172
    _globals["_DHT_FETCH_RESPONSE"]._serialized_end = 315
    _globals["_DHT_STORE_REQUEST"]._serialized_start = 318
    _globals["_DHT_STORE_REQUEST"]._serialized_end = 473
    _globals["_DHT_STORE_RESPONSE"]._serialized_start = 476
    _globals["_DHT_STORE_RESPONSE"]._serialized_end = 617
    _globals["_DHT_DELETE_REQUEST"]._serialized_start = 620
    _globals["_DHT_DELETE_REQUEST"]._serialized_end = 761
    _globals["_DHT_DELETE_RESPONSE"]._serialized_start = 763
    _globals["_DHT_DELETE_RESPONSE"]._serialized_end = 821
    _globals["_DHT_DELETE_NOTICE_REQUEST"]._serialized_start = 823
    _globals["_DHT_DELETE_NOTICE_REQUEST"]._serialized_end = 913
    _globals["_DHT_DELETE_NOTICE_RESPONSE"]._serialized_start = 915
    _globals["_DHT_DELETE_NOTICE_RESPONSE"]._serialized_end = 980
    _globals["_DHT_UPDATE_REQUEST"]._serialized_start = 982
    _globals["_DHT_UPDATE_REQUEST"]._serialized_end = 1080
    _globals["_DHT_UPDATE_NOTICE_REQUEST"]._serialized_start = 1082
    _globals["_DHT_UPDATE_NOTICE_REQUEST"]._serialized_end = 1187
    _globals["_DHT_UPDATE_RESPONSE"]._serialized_start = 1189
    _globals["_DHT_UPDATE_RESPONSE"]._serialized_end = 1247
    _globals["_DHT_UPDATE_NOTICE_RESPONSE"]._serialized_start = 1249
    _globals["_DHT_UPDATE_NOTICE_RESPONSE"]._serialized_end = 1314
    _globals["_DHT_REGISTER_NOTICES_REQUEST"]._serialized_start = 1316
    _globals["_DHT_REGISTER_NOTICES_REQUEST"]._serialized_end = 1409
    _globals["_DHT_REGISTER_NOTICES_RESPONSE"]._serialized_start = 1411
    _globals["_DHT_REGISTER_NOTICES_RESPONSE"]._serialized_end = 1516
    _globals["_PING"]._serialized_start = 1518
    _globals["_PING"]._serialized_end = 1539
    _globals["_PONG"]._serialized_start = 1541
    _globals["_PONG"]._serialized_end = 1562
    _globals["_TASKALLOCATE_REQUEST"]._serialized_start = 1564
    _globals["_TASKALLOCATE_REQUEST"]._serialized_end = 1626
    _globals["_TASKALLOCATE_RESPONSE"]._serialized_start = 1628
    _globals["_TASKALLOCATE_RESPONSE"]._serialized_end = 1688
    _globals["_SENDEVENT_REQUEST"]._serialized_start = 1690
    _globals["_SENDEVENT_REQUEST"]._serialized_end = 1752
    _globals["_SENDEVENT_RESPONSE"]._serialized_start = 1754
    _globals["_SENDEVENT_RESPONSE"]._serialized_end = 1843
    _globals["_BOOTSTRAP_REQUEST"]._serialized_start = 1845
    _globals["_BOOTSTRAP_REQUEST"]._serialized_end = 1927
    _globals["_BOOTSTRAP_RESPONSE"]._serialized_start = 1929
    _globals["_BOOTSTRAP_RESPONSE"]._serialized_end = 1990
    _globals["_BOOTSTRAP_ITEM"]._serialized_start = 1992
    _globals["_BOOTSTRAP_ITEM"]._serialized_end = 2067
    _globals["_HEARTBEAT_REQUEST"]._serialized_start = 2069
    _globals["_HEARTBEAT_REQUEST"]._serialized_end = 2109
    _globals["_HEARTBEAT_RESPONSE"]._serialized_start = 2111
    _globals["_HEARTBEAT_RESPONSE"]._serialized_end = 2152
    _globals["_SENDMONITOR_REQUEST"]._serialized_start = 2154
    _globals["_SENDMONITOR_REQUEST"]._serialized_end = 2250
    _globals["_SENDMONITOR_RESPONSE"]._serialized_start = 2252
    _globals["_SENDMONITOR_RESPONSE"]._serialized_end = 2311
    _globals["_SENDCHECKPOINT_REQUEST"]._serialized_start = 2313
    _globals["_SENDCHECKPOINT_REQUEST"]._serialized_end = 2412
    _globals["_SENDCHECKPOINT_RESPONSE"]._serialized_start = 2414
    _globals["_SENDCHECKPOINT_RESPONSE"]._serialized_end = 2476
    _globals["_DHTSERVICE"]._serialized_start = 2622
    _globals["_DHTSERVICE"]._serialized_end = 3218
    _globals["_TASKSERVICE"]._serialized_start = 3221
    _globals["_TASKSERVICE"]._serialized_end = 3484
    _globals["_PEERSERVICE"]._serialized_start = 3486
    _globals["_PEERSERVICE"]._serialized_end = 3573
    _globals["_KEEPALIVESERVICE"]._serialized_start = 3576
    _globals["_KEEPALIVESERVICE"]._serialized_end = 3718
# @@protoc_insertion_point(module_scope)
