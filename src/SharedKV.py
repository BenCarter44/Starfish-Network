
import binascii
import os
import threading
import time
from typing import Dict
import zmq

from MessageFormats import PeerKV, PeerKV_Hello, PeerKV_Hello_Receipt, dump
from ttl import DataWithTTL


def zpipe(ctx):
    """build inproc pipe for talking to threads

    mimic pipe used in czmq zthread_fork.

    Returns a pair of PAIRs connected via inproc
    """
    a = ctx.socket(zmq.PAIR)
    b = ctx.socket(zmq.PAIR)
    a.linger = b.linger = 0
    a.hwm = b.hwm = 1
    iface = "inproc://%s" % binascii.hexlify(os.urandom(8))
    a.bind(iface)
    b.connect(iface)
    return a,b

class KeyValueCommunications():
    def __init__(self, serving_endpoint_pub, serving_endpoint_query, my_identity):
        
        self.context = zmq.Context()
        self.my_identity = my_identity
        self.serving_endpoint_pub = serving_endpoint_pub
        self.serving_endpoint_query = serving_endpoint_query
        self.ttl = 60
        # sockets for binding to receive connections from peers

        self.publish_update_socket = self.context.socket(zmq.PUB)
        self.publish_update_socket.bind(serving_endpoint_pub)
        
        self.receive_query_socket = self.context.socket(zmq.ROUTER)
        self.receive_query_socket.bind(serving_endpoint_query)

        

        # sockets for connecting to peers 
        self.peer_subscribe_socket = self.context.socket(zmq.SUB)
        # self.peer_subscribe_socket.setsockopt(zmq.IDENTITY,my_identity)
        self.peer_query_socket = self.context.socket(zmq.DEALER)
        self.peer_query_socket.setsockopt(zmq.IDENTITY,my_identity)

        self.peers = {} # DataTTL() dictionary by time.

        self.keyvalues : Dict[str, DataWithTTL] = {} # IP is key. TTL is value.

        key = f"{serving_endpoint_pub}/P"
        self.keyvalues[key] = DataWithTTL(key, self.ttl + time.time())
        key = f"{serving_endpoint_query}/Q"
        self.keyvalues[key] = DataWithTTL(key, self.ttl + time.time())

        self.control_socket_outside, inside_socket = zpipe(self.context)

        self.th = threading.Thread(None,self.handle_responses,args=(inside_socket,),name="KeyVal Management")
        self.th.start()

        self.ticker = {}
        self.ticker["connect-peer"] = -1
        self.ticker["state-request"] = 10
        self.state_replay = 0


    def connect_to_peer(self, endpoint_publish_point, endpoint_query):
        self.peer_subscribe_socket.connect(endpoint_publish_point)
        self.peer_query_socket.connect(endpoint_query)
    
        self.send_hello()

    def send_state_request_to_peers(self):
        pk = PeerKV()
        pk.fetch_state_command()
        self.ticker["state-request"] = time.time() + 10
        self.peer_query_socket.send_multipart(pk.compile())
        

    def send_hello(self):
         # Currently, this will be sent to ALL connected peers (dealer socket)
        msg = PeerKV_Hello()
        msg.create(self.serving_endpoint_pub,
                   self.serving_endpoint_query,
                   self.ttl + time.time()
                   )
        self.ticker["connect-peer"] = time.time() + 10 # 10 sec timeout!
        self.peer_query_socket.send_multipart(msg.compile())
        print("Sent hello!")

    def stop(self):
        self.control_socket_outside.send_string("STOP")
        self.th.join()

    # to be run by a thread!
    def handle_responses(self,status_socket : zmq.Socket):
        poller = zmq.Poller() # put number in here if you want a timeout
        poller.register(self.receive_query_socket, zmq.POLLIN)
        poller.register(self.peer_subscribe_socket, zmq.POLLIN)
        poller.register(self.peer_query_socket, zmq.POLLIN)
        poller.register(status_socket, zmq.POLLIN)

        while True:
            socket_receiving = dict(poller.poll(5000))
            
            if(status_socket in socket_receiving):
                msg = status_socket.recv_string()
                if(msg == "STOP"):
                    break

            if(self.receive_query_socket in socket_receiving):
                msg = self.receive_query_socket.recv_multipart()
                identity = msg[0]
                data = msg[1:]
                print("Received ",time.time())
                dump(msg)
                if(data[0] == b'Hello!'):
                    pk = PeerKV_Hello()
                    pk.import_msg(data)

                    endpoints = pk.get_endpoints()
                    endpt_pub = endpoints[0].get_value_or_null()
                    endpt_query = endpoints[1].get_value_or_null()
                    if(not(endpt_pub is None or endpt_query is None)):

                        self.peers[f"{identity}-pub"] = endpoints[0].get_value_or_null()
                        self.peers[f"{identity}-query"] = endpoints[1].get_value_or_null()

                        key = f"{endpt_pub}/P"
                        self.keyvalues[key] = DataWithTTL(key, self.ttl + time.time())
                        key = f"{endpt_query}/Q"
                        self.keyvalues[key] = DataWithTTL(key, self.ttl + time.time())

                    pk_response = PeerKV_Hello_Receipt()
                    pk_response.create()
                    self.receive_query_socket.send_multipart(
                        pk_response.compile_with_address(identity))
                    print('Sent response to hello!', time.time())          

                elif(data[0] == b'General'):
                    pk = PeerKV()
                    pk_response = PeerKV()
                    pk.import_msg(data)
                    if(pk.is_fetch_state()):
                        results = []
                        for val in self.keyvalues:
                            if(self.keyvalues[val].is_valid()):
                                results.append(self.keyvalues[val])

                        pk_response.return_state_receipt(results)
                        self.receive_query_socket.send_multipart(
                            pk_response.compile_with_address(identity))
                        print('Sent response to general state request!', time.time())        

                else:
                    raise ValueError("Unknown message received from Query Router Socket")
            
            if(self.peer_query_socket in socket_receiving):
                msg = self.peer_query_socket.recv_multipart()

                if(msg[0] == b'Welcome'):
                    pk = PeerKV_Hello_Receipt()
                    pk.import_msg(msg)
                    self.ticker["connect-peer"] = 0 # done!      
                    print("Connected!") 
                    self.send_state_request_to_peers()  # send request for state.
                
                elif(msg[0] == b'General'):
                    pk = PeerKV()
                    pk.import_msg(msg)
                    if(pk.is_return_state()):
                        state = pk.get_state_from_return()
                        
                        # merge the key values together.
                        for key in state:
                            k = key.get_value_or_null()
                            if(k is None):
                                continue
                            if(k in self.keyvalues and key.get_timeout() > self.keyvalues[k].get_timeout()):
                                self.keyvalues[k] = key
                            elif(not(k in self.keyvalues)):
                                self.keyvalues[k] = key
                        print("Received state. Merged in.")
                        self.ticker["state-request"] = 0

                else:
                    raise ValueError("Unknown message received from Peer Dealer Socket")
            
            if(self.ticker["connect-peer"] > 100 and self.ticker["connect-peer"] < time.time()):
                # resend hello!
                print("Resending Hello!")             
                self.send_hello()
            
            if(self.ticker["state-request"] > 100 and self.ticker["state-request"] < time.time() and self.state_replay < 10):
                # resend hello!
                print("Resending state request!") 
                self.state_replay += 1            
                self.send_state_request_to_peers()
            

    





        
