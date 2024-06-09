
import binascii
import datetime
import os
import threading
import time
from typing import Dict, List, Set
import zmq

from MessageFormats import *
from ReliabilityEngine import *
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
        self.ttl = 60 + time.time() # TODO: Implement heart beating and real TTLs.
        # sockets for binding to receive connections from peers

        self.publish_update_socket = self.context.socket(zmq.PUB)
        self.publish_update_socket.bind(serving_endpoint_pub)
        
        self.receive_query_socket = self.context.socket(zmq.ROUTER)
        self.receive_query_socket.bind(serving_endpoint_query)
        self.receive_query_socket_RE = ReliabilityEngine(self.receive_query_socket)

        # sockets for connecting to peers 
        self.peer_subscribe_socket = self.context.socket(zmq.SUB)
        # self.peer_subscribe_socket.setsockopt(zmq.IDENTITY,my_identity)
        self.peer_query_socket = self.context.socket(zmq.DEALER)
        self.peer_query_socket_RE = ReliabilityEngine(self.peer_query_socket)
        # TODO: Design Decision: Dealer sends communications to ALL connected peers
        # self.peer_query_socket.setsockopt(zmq.IDENTITY,my_identity)
        # TODO: Identity is not required here. (Key Value doesn't have identity.)

        self.endpoints_kv : Dict[str, DataWithTTL] = {} # IP is key. TTL is value.

        self.connected_peers : Set[str] = set()

        key = f"{serving_endpoint_pub}/P"
        self.endpoints_kv[key] = DataWithTTL(key, self.ttl)
        key = f"{serving_endpoint_query}/Q"
        self.endpoints_kv[key] = DataWithTTL(key, self.ttl)

        self.control_socket_outside, inside_socket = zpipe(self.context)

        self.open_messages : Dict[str, ReliableMessage] = {}
        self.open_message_data : Dict[str, any] = {}

        self.th = threading.Thread(None,self.handle_responses,args=(inside_socket,),name="KeyVal Management")
        self.th.start()

        

    # TODO: Structure:
    #   Interface: 
    #       connect to peer
    #       get endpoints
    #       get connected peers
    #       disconnect from peer
    #       stop
    #
    #   Protocol Methods:
    #       send_hello() / finish_hello()
    #       send_state_request() / finish_state_request()
    #       push_peer_updates()
    #       push_new_value()
    #       
    #   Receiving methods:
    #       receiving_hello()
    #       answer_state_request()
    #       subscribed_updates()
    #       answer_new_value()
    #       
    #       
    #   Thread methods:
    #      handle_responses()
    #          delegates receiving msgs to the receiving methods
    #   
    #   Reliability Engine
    #      needs it's own class.... 
    #      reliable_message = add_message(msg, retry_gap=10sec, max_retry=5)
    #      reliable_message.mark_done()
    #      reliable_message.is_complete()
    #

    def connect_to_peer(self, endpoint_publish_point, endpoint_query):
        self.peer_subscribe_socket.connect(endpoint_publish_point)
        self.peer_query_socket.connect(endpoint_query)

        r = random.randint(0,32766)
        while f"hello-{r}" in self.open_messages:  # TODO: Instead of R, do hash of data.
            r = random.randint(0,32766)

        self.open_message_data[f"hello-{r}"] = {"pub": endpoint_publish_point,
                                                "query": endpoint_query,
                                                "done" : False}
        self.__send_hello(r)
        
        # wait for it to be done!
        while not(self.open_message_data[f"hello-{r}"]["done"]):
            time.sleep(0.001) # try every 10 msec
        
        self.peer_subscribe_socket.subscribe("IP Update") # subscribe after the hello.
        
        self.__send_state_request(r)
        self.open_message_data[f"state-{r}"] = {"done" : False}

        # wait for it to be done!
        while not(self.open_message_data[f"state-{r}"]["done"]):
            time.sleep(0.001) # try every 10 msec
        
        

    def get_endpoints(self):
        return self.endpoints_kv

    def disconnect_from_peer(self, endpoint_publish_point, endpoint_query):
        self.peer_subscribe_socket.disconnect(endpoint_publish_point)
        self.peer_query_socket.disconnect(endpoint_query)

        key = f"{endpoint_publish_point}/P"
        self.connected_peers.remove(key)
        key = f"{endpoint_query}/Q"
        self.connected_peers.remove(key)

    def stop(self):
        self.peer_query_socket_RE.stop()
        self.receive_query_socket_RE.stop()
        self.control_socket_outside.send_string("STOP")
        self.th.join()
    
    def pretty_print_endpoint_kv(self, title="Endpoints:"):
        out_debug = title + "\n"
        out_debug += "\t IP \t\t | \t IP-val \t\t | \t EXP \t \n"
        for x in self.endpoints_kv:
            tm = self.endpoints_kv[x].get_timeout()
            nice = datetime.datetime.fromtimestamp(tm)
            out_debug += f"\t{x} \t | \t {self.endpoints_kv[x].get_value_or_null()} \t | \t{nice}\n"
        out_debug += '---'
        print(out_debug)

    # Protocol Methods -------------------------------- No blocking allowed in all finishes.
    # All finishes too must be idempotent (assume req's are replayed)

    def __send_hello(self, r_identity : int):
         # TODO: Design Decision. Currently, this will be sent to ALL connected peers (dealer socket)
        msg = PeerKV_Hello()
        
        msg.create(
                   r_identity, 
                   self.serving_endpoint_pub + "/P",
                   self.serving_endpoint_query + "/Q",
                   self.ttl,
                   )
        print("Sending hello!")
        rm = self.peer_query_socket_RE.add_message(msg.compile(), 10, 25)
        self.open_messages[f"hello-{r_identity}"] = rm

    def __finish_hello(self, msg : PeerKV_Hello):
        r = msg.get_r_identity()
        if(self.open_messages[f"hello-{r}"].is_complete()):
            return # don't need to answer. Already received response due to dealer.
        self.open_messages[f"hello-{r}"].mark_done() 
        request_data = self.open_message_data[f"hello-{r}"]
       
        key = f"{request_data['pub']}/P"
        # NO BLOCKING UPDATES IN THREAD!
        endpoints = msg.get_endpoints()
        self.__update_keyval(key,  endpoints[0], True)
        self.connected_peers.add(key)

        key = f"{request_data['query']}/Q"
        self.__update_keyval(key,  endpoints[1], True)

        self.connected_peers.add(key)

        request_data["done"] = True # passes by ref.

    def __send_state_request(self, r):
        pk = PeerKV()
        pk.fetch_state_command(r_identity=r)
        rm = self.peer_query_socket_RE.add_message(pk.compile(), 10, 5) 
        self.open_messages[f"state-{r}"] = rm
    
    def __finish_state_request(self, msg: PeerKV):
        state = msg.get_state_from_return()
        if(self.open_messages[f"state-{msg.get_r_identity()}"].is_complete()):
            return # don't need to answer. Already received response due to dealer.
        
        # merge the key values together.
        for key in state:
            k = key.get_value_or_null()
            if(k is None):
                continue
            # TODO: Design Decision. State requests do not count for updates. 
            if(k in self.endpoints_kv and key.get_timeout() > self.endpoints_kv[k].get_timeout()):
                self.endpoints_kv[k] = key
            elif(not(k in self.endpoints_kv)):
                self.endpoints_kv[k] = key
       
        r = msg.get_r_identity()
        self.open_messages[f"state-{r}"].mark_done() 
        request_data = self.open_message_data[f"state-{r}"]
        request_data["done"] = True # passes by ref.


    def __update_keyval(self, key : str, val : DataWithTTL, ownership=False):
        # push changes. Ownership is if you made it.

        if(not(val.is_valid())):
            return
        
        if(key in self.endpoints_kv and self.endpoints_kv[key].get_value_or_null() == val.get_value_or_null() and self.endpoints_kv[key].get_timeout() >= val.get_timeout()):
            return # No change!

        self.endpoints_kv[key] = val
        pk = PeerKV_Subscribe()  # TODO: Add "repeat-missing" updates!
        pk.create("IP Update")
        pk.set_key(key)
        pk.set_value(val)
        
        self.publish_update_socket.send_multipart(pk.compile())

        self.pretty_print_endpoint_kv("Endpoints Changed:")

        if(not(ownership)):
            return
        
        # You owned these changes!

        pk = PeerKV()
        r = random.randint(0,32766)
        while f"push-change-{r}" in self.open_messages:  # TODO: Instead of R, do hash of data.
            r = random.randint(0,32766)
        pk.push_change(key, val, r)
        rm = self.peer_query_socket_RE.add_message(pk.compile(), 5, 2)
        self.open_message_data[f"push-change-{r}"] = {"done" : False}
        self.open_messages[f"push-change-{r}"] = rm

        
        # wait for it to be done! (Makes it blocking now TODO: Design Decision!)
        # while not(self.open_message_data[f"push-change-{r}"]["done"]):
        #     time.sleep(1) # try every 10 msec
        #     print('Blocked')

    def __finish_update_keyval(self, msg : PeerKV):
        r = msg.get_r_identity()
        if(self.open_messages[f"push-change-{r}"].is_complete()):
            return # don't need to answer. Already received response due to dealer.
        self.open_messages[f"push-change-{r}"].mark_done() 
        request_data = self.open_message_data[f"push-change-{r}"]
        request_data["done"] = True # passes by ref.

    # Receiving methods ----------------------- No blocking allowed!

    def __receiving_hello(self, msg : PeerKV_Hello, address : bytes):
        endpoints = msg.get_endpoints()
        endpt_pub = endpoints[0].get_value_or_null()
        endpt_query = endpoints[1].get_value_or_null() # TODO: Currently does not save if passed in TTL is 0
        if(not(endpt_pub is None or endpt_query is None)):
            self.__update_keyval(endpt_pub,  endpoints[0], True)
            self.__update_keyval(endpt_query,  endpoints[1], True)

        # doesn't matter for retries.
        pk_response = PeerKV_Hello()
        pk_response.create(
                   msg.get_r_identity(), 
                   self.serving_endpoint_pub + "/P",
                   self.serving_endpoint_query + "/Q",
                   self.ttl,
                   )
        pk_response.set_welcome()
        self.receive_query_socket.send_multipart(
            pk_response.compile_with_address(address))
    
    def __subscribed_updates(self, msg : PeerKV_Subscribe):
        key = msg.get_key()
        val = msg.get_value()

        if(not(key in self.endpoints_kv)):
            self.__update_keyval(key,  val)

        # TODO: Better merging here.
        elif(val.get_timeout() > self.endpoints_kv[key].get_timeout()):
             self.__update_keyval(key,  val)
    
    def __answer_state_request(self, msg : PeerKV, address : bytes):
        pk_response = PeerKV()
        results = []
        for val in self.endpoints_kv:
            if(self.endpoints_kv[val].is_valid()):
                results.append(self.endpoints_kv[val])

        pk_response.return_state_receipt(results, msg.get_r_identity())
        self.receive_query_socket.send_multipart(
            pk_response.compile_with_address(address))
    
    def __answer_pushed_change(self, msg : PeerKV, address : bytes):
        pk_response = PeerKV()
        key, val = msg.get_push_key_val()

        self.__update_keyval(key, val)
        
        pk_response.return_push_change(msg.get_r_identity())

        self.receive_query_socket.send_multipart(
            pk_response.compile_with_address(address))
    

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

            if(self.peer_subscribe_socket in socket_receiving):
                msg = self.peer_subscribe_socket.recv_multipart()
                # print("Received on peer subscribe socket: ",time.time())
                # dump(msg)
                # print("---\n")
                pk = PeerKV_Subscribe()
                pk.import_msg(msg)
                self.__subscribed_updates(pk)

            if(self.receive_query_socket in socket_receiving):
                msg = self.receive_query_socket.recv_multipart()
                addr = msg[0]
                data = msg[1:]
                # print("Received on receiving query socket: ",time.time())
                # dump(msg)
                # print("---\n")
                if(data[0] == b'Hello!'):
                    pk = PeerKV_Hello()
                    pk.import_msg(data)
                    self.__receiving_hello(pk, addr)
                           
                elif(data[0] == b'General'):
                    pk = PeerKV()
                    pk.import_msg(data)
                    if(pk.is_fetch_state()):
                        self.__answer_state_request(pk, addr)
                    elif(pk.is_push_change()):
                        self.__answer_pushed_change(pk, addr) 
                else:
                    raise ValueError("Unknown message received from Query Router Socket")
            
            if(self.peer_query_socket in socket_receiving):
                msg = self.peer_query_socket.recv_multipart()
                # print("Received on peer query socket: ",time.time())
                # dump(msg)
                # print("---\n")

                if(msg[0] == b'Welcome'):
                    pk = PeerKV_Hello()
                    pk.import_msg(msg)
                    self.__finish_hello(pk)
                
                elif(msg[0] == b'General'):
                    pk = PeerKV()
                    pk.import_msg(msg)
                    if(pk.is_return_state()):
                        self.__finish_state_request(pk)
                    elif(pk.is_push_change_receive()):
                        self.__finish_update_keyval(pk)

                else:
                    raise ValueError("Unknown message received from Peer Dealer Socket")
            
    





        
