


import time
from SharedKV import KeyValueCommunications


id1 = b"John Smith"
endpoint_pub1 = "tcp://127.0.0.1:8008"
endpoint_query1 = "tcp://127.0.0.1:8009"
kvcomm = KeyValueCommunications(endpoint_query1, 101)

print("Finished setting up ports!")

connect_endpoint_pub2 = "tcp://127.0.0.1:8018"
connect_endpoint_query2 = "tcp://127.0.0.1:8019"

print("Attempting to connect to peer.")
kvcomm.connect_to_peer(connect_endpoint_query2)

count = 0
while True:
    # if(kvcomm.endpoints_modified()):
    print(count)
    count += 1
    kvcomm.pretty_print_endpoint_kv()
    #     kvcomm.reset_modify()

    kvcomm.send_dummy()
    time.sleep(1)
kvcomm.stop()