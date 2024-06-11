


import random
import threading
import time
from SharedKV import KeyValueCommunications


neighbors = {101:[102], 102:[103,104], 104:[105], 105:[103], 103:[101]}


def main_worker(identity):
    kvcomm = KeyValueCommunications(f"tcp://127.0.0.1:8{identity}",f"tcp://127.0.0.1:9{identity}",identity)
    time.sleep(identity % 7 + 2)
    for x in neighbors[identity]:
        kvcomm.connect_to_peer(f"tcp://127.0.0.1:8{x}",f"tcp://127.0.0.1:9{x}")

    print("Connected")
    time.sleep(identity % 7 + 2)
    
    while True:
        if(random.random() < 0.1):
            kvcomm.send_dummy()
        time.sleep(1)
        print(f"Node: {identity}")
        f = open(f"{identity}.log",'w')
        f.write(kvcomm.string_print_endpoint_kv())
        f.close()
        if(random.random() < 0.004):
            print(f'{identity} Disconnect')
            break
    kvcomm.stop()




for id_num in range(101,105+1):
    th = threading.Thread(None, main_worker, args=(id_num, ))
    th.start()

th.join()