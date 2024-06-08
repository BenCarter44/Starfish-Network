


from SharedKV import KeyValueCommunications


id1 = b"John Smith"
endpoint_pub1 = "tcp://127.0.0.1:8008"
endpoint_query1 = "tcp://127.0.0.1:8009"
kvcomm = KeyValueCommunications(endpoint_pub1, endpoint_query1, id1)

print("Finished setting up ports!")

connect_endpoint_pub2 = "tcp://127.0.0.1:8018"
connect_endpoint_query2 = "tcp://127.0.0.1:8019"

kvcomm.connect_to_peer(connect_endpoint_pub2, connect_endpoint_query2)


input("Delay2\n")

kvcomm.stop()

print(kvcomm.peers)
print(kvcomm.keyvalues)