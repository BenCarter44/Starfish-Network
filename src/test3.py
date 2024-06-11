


import random
import time
from SharedKV import KeyValueCommunications


id3 = b"Pizza"
endpoint_pub3 = "tcp://127.0.0.1:8028"
endpoint_query3 = "tcp://127.0.0.1:8029"
kvcomm = KeyValueCommunications(endpoint_pub3, endpoint_query3, id3)

print("Finished setting up ports!")

connect_endpoint_pub2 = "tcp://127.0.0.1:8018"
connect_endpoint_query2 = "tcp://127.0.0.1:8019"

print("Attempting to connect to peer.")
kvcomm.connect_to_peer(connect_endpoint_pub2, connect_endpoint_query2)

count = 0
for x in range(3):
    # if(kvcomm.endpoints_modified()):
    print(count)
    count += 1
    kvcomm.pretty_print_endpoint_kv()
    #     kvcomm.reset_modify()

    kvcomm.send_dummy()
    time.sleep(random.randint(3,5))
kvcomm.stop()