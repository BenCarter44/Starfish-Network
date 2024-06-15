
import time
from SharedKV import KeyValueCommunications


id2 = b"Apple Pie"
endpoint_pub2 = "tcp://127.0.0.1:8018"
endpoint_query2 = "tcp://127.0.0.1:8019"
kvcomm = KeyValueCommunications(endpoint_query2, 102)

print("Finished setting up ports!")

connect_endpoint_pub1 = "tcp://127.0.0.1:8008"
connect_endpoint_query1 = "tcp://127.0.0.1:8009"

# kvcomm.connect_to_peer(connect_endpoint_pub1, connect_endpoint_query1)

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