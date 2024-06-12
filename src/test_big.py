


import random
import threading
import time

import zmq
from SharedKV import KeyValueCommunications, zpipe




# neighbors = {101:[102], 102:[103,104], 104:[105], 105:[103], 103:[101]}


def main_worker(identity, control : zmq.Socket):
    kvcomm = KeyValueCommunications(f"tcp://127.0.0.1:8{identity}",f"tcp://127.0.0.1:9{identity}",identity)

    poller = zmq.Poller()
    poller.register(control, zmq.POLLIN)
    while True:
        socket_recv = dict(poller.poll(1000))
        if(control in socket_recv):
            msg = control.recv_multipart()
            if(msg[0] == b'Connect'):
                peer = int.from_bytes(msg[1],'big')
                if(peer == identity):
                    # error!
                    kvcomm.printf("Test : Error - Can't connect to itself")
                    continue
                
                kvcomm.connect_to_peer(f"tcp://127.0.0.1:8{peer}",f"tcp://127.0.0.1:9{peer}")
                kvcomm.printf(f"Test : Connected to {peer}")
            if(msg[0] == b'Disconnect'):
                peer = int.from_bytes(msg[1],'big')
                if(peer == identity):
                    # error!
                    kvcomm.printf("Test : Error - Can't connect to itself")
                    continue
                
                kvcomm.disconnect_from_peer(f"tcp://127.0.0.1:8{peer}",f"tcp://127.0.0.1:9{peer}")
                kvcomm.printf(f"Test : Disconnected from {peer}")
            if(msg[0] == b'SendData'):
                kvcomm.printf(f"Test : Send Dummy")
                kvcomm.send_dummy()
            if(msg[0] == b'STOP'):
                break
            if(msg[0] == b'print'):
                kvcomm.printf(kvcomm.string_print_endpoint_kv())

    kvcomm.stop()

ctx = zmq.Context()

peers = {}
for id_num in range(101,110+1):
    mine, theirs = zpipe(ctx)
    th = threading.Thread(None, main_worker, args=(id_num, theirs))
    th.start()
    peers[id_num] = {"th":th, "soc":mine}

while True:
    print("What would you like to do? ")
    c = ''
    try:
        c = input("/? \n")
    except KeyboardInterrupt:
        c = 'exit'
    if(c == 'exit'):
        for peer in peers:
            peers[peer]["soc"].send_multipart([b'STOP'])
            peers[peer]["th"].join()
            print(f"Quit {peer}")
        break

    if(c.find('disconnect') != -1):
        # first is node origin
        # second is the node to connect to 
        c_tokens = c.split(" ")
        try:
            for x in range(1,len(c_tokens)):
                c_tokens[x] = int(c_tokens[x])
            if(len(c_tokens) < 3):
                raise ValueError
        except:
            print("Bad command")
            continue
        if(c_tokens[1] in peers):
            peers[c_tokens[1]]["soc"].send_multipart([b'Disconnect',int.to_bytes(int(c_tokens[2]),1,'big')])
            # time.sleep(1)
            # peers[c_tokens[2]]["soc"].send_multipart([b'Disconnect',int.to_bytes(int(c_tokens[1]),1,'big')])
        else:
            print("Unknown peer")
        continue

    if(c.find('connect') != -1):
        # first is node origin
        # second is the node to connect to 
        c_tokens = c.split(" ")
        try:
            for x in range(1,len(c_tokens)):
                c_tokens[x] = int(c_tokens[x])
            if(len(c_tokens) < 3):
                raise ValueError
        except:
            print("Bad command")
            continue
        if(c_tokens[1] in peers):
            peers[c_tokens[1]]["soc"].send_multipart([b'Connect',int.to_bytes(int(c_tokens[2]),1,'big')])
            # time.sleep(1)
            # peers[c_tokens[2]]["soc"].send_multipart([b'Connect',int.to_bytes(int(c_tokens[1]),1,'big')])
        else:
            print("Unknown peer")
        continue
    
    
    if(c.find('send') != -1):
        # first is node origin
        # second is the node to connect to 
        c_tokens = c.split(" ")
        try:
            for x in range(1,len(c_tokens)):
                c_tokens[x] = int(c_tokens[x])
            if(len(c_tokens) < 2):
                raise ValueError
        except:
            print("Bad command")
            continue
        if(c_tokens[1] in peers):
            peers[c_tokens[1]]["soc"].send_multipart([b'SendData'])
        else:
            print("Unknown peer")
        continue
    
    if(c.find('print') != -1):
        # first is node origin
        # second is the node to connect to 
        c_tokens = c.split(" ")
        try:
            for x in range(1,len(c_tokens)):
                c_tokens[x] = int(c_tokens[x])
            if(len(c_tokens) < 2):
                raise ValueError
        except:
            print("Bad command")
            continue
        if(c_tokens[1] in peers):
            peers[c_tokens[1]]["soc"].send_multipart([b'print'])
        else:
            print("Unknown peer")
        continue

    print("Unknown command \n")
print("Done")