
import binascii
import datetime
import os
import threading
import time
from typing import Dict, List, Set
import zmq

from MessageFormats import *
from ReliabilityEngine import *
from ttl import IP_TTL


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
        # self.ttl = 60 + time.time() # TODO: Implement heart beating and real TTLs.
        # sockets for binding to receive connections from peers

        self.publish_update_socket = self.context.socket(zmq.PUB)
        self.publish_update_socket.bind(serving_endpoint_pub)
        
        self.receive_query_socket = self.context.socket(zmq.ROUTER)
        self.receive_query_socket.bind(serving_endpoint_query)

        # sockets for connecting to peers 
        self.peer_subscribe_socket = self.context.socket(zmq.SUB)
        # self.peer_subscribe_socket.setsockopt(zmq.IDENTITY,my_identity)
        peer_query_socket = self.context.socket(zmq.DEALER)
        peer_query_socket.hwm = 1000

        self.peer_query_socket_incoming, output = zpipe(self.context)

        self.peer_query_socket_RE = ReliabilityEngine(self.context, peer_query_socket, output)
        # TODO: Design Decision: Dealer sends communications to ALL connected peers
        # self.peer_query_socket.setsockopt(zmq.IDENTITY,my_identity)
        # TODO: Identity is not required here. (Key Value doesn't have identity.)

        # self.endpoints_kv : Dict[str, DataWithTTL] = {} # IP is key. TTL is value.
        self.endpoints_kv : Dict[str, IP_TTL] = {}

        self.marking_use : Dict[bytes, str] = {}
        self.connected_peers : Set[str] = set()
        self.new_data = False
        # do not add yourself, others will tell you the TTL.

       
        key = f"{serving_endpoint_pub}/P"
        ttl = IP_TTL()
        ttl.create(serving_endpoint_pub, time.time() + 10) # personal one (not owned though). Assume you'll last 10 sec
        self.endpoints_kv[key] = ttl

        key = f"{serving_endpoint_query}/Q"
        ttl = IP_TTL()
        ttl.create(serving_endpoint_query, time.time() + 10) # personal one (not owned though). Assume you'll last 10 sec
        self.endpoints_kv[key] = ttl

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
        i = self.peer_query_socket_RE.get_number_peers()
        self.peer_query_socket_RE.add_peer(endpoint_query)
        i2 = self.peer_query_socket_RE.get_number_peers()
        while(i == i2): # wait for connect.
            i2 = self.peer_query_socket_RE.get_number_peers()
            time.sleep(0.01)

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
        self.peer_query_socket_RE.remove_peer(endpoint_query)

        key = f"{endpoint_publish_point}/P"
        self.connected_peers.remove(key)
        key = f"{endpoint_query}/Q"
        self.connected_peers.remove(key)

    def stop(self):
        self.peer_query_socket_RE.stop()
        self.control_socket_outside.send_string("STOP")
        self.th.join()
    
    def endpoints_modified(self):
        i = self.new_data
        return i
    
    def reset_modify(self):
        self.new_data = False

    def pretty_print_endpoint_kv(self, title="Endpoints:"):
        out_debug = title + "\n"
        out_debug += "\t IP \t\t\t | \t IP-val \t\t\t | \t EXP \t \n"
        print(out_debug)
        for x in self.endpoints_kv:
            print(x, end=' | ')
            self.endpoints_kv[x].display()
    
    def string_print_endpoint_kv(self, title="Endpoints:"):
        out_debug = title + "\n"
        out_debug += "\t IP \t\t\t | \t IP-val \t\t\t | \t EXP \t \n"
        for x in self.endpoints_kv:
            out_debug += str(x) + ' | '
            out_debug += self.endpoints_kv[x].display_string() + "\n"
        return out_debug

        
    def prune_endpoints(self):
        for endpoint in list(self.endpoints_kv.keys()):
            if(self.endpoints_kv[endpoint].get_ip_or_null() is None):
                if(endpoint in self.connected_peers):
                    print(f"Peer {endpoint} disconnected!")
                    self.connected_peers.remove(endpoint)
                
                del self.endpoints_kv[endpoint]
                self.new_data = True


    # Protocol Methods -------------------------------- No blocking allowed in all finishes.
    # All finishes too must be idempotent (assume req's are replayed)

    def send_dummy(self):
        msg = BasicMultipartMessage()
        msg.set_val(b"Random")
        self.peer_query_socket_RE.add_message(msg.compile(), 0, 1)

    def __send_hello(self, r_identity : int):
         # TODO: Design Decision. Currently, this will be sent to ALL connected peers (dealer socket)
        msg = PeerKV_Hello()
        
        msg.create(
                   r_identity, 
                   self.serving_endpoint_pub + "/P",
                   self.serving_endpoint_query + "/Q",
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
       
        # NO BLOCKING UPDATES IN THREAD!
        endpoints = msg.get_endpoints()
        ttl = IP_TTL()
        ttl.create(endpoints[0][:-2], time.time() + 10)
        self.__update_keyval(endpoints[0],  ttl, distribute=True)
        self.connected_peers.add(endpoints[0])

        ttl = IP_TTL()
        ttl.create(endpoints[1][:-2], time.time() + 10)
        self.__update_keyval(endpoints[1], ttl, distribute=True)

        self.connected_peers.add(endpoints[1])

        request_data["done"] = True # passes by ref.
        if("next-state" in request_data):
            self.__send_state_request(r)
            self.open_message_data[f"state-{r}"] = {"done" : False}

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
        for state_val in state:
            key = state_val[0]
            val = state_val[1]
            if(val is None):
                continue

            ttl = IP_TTL()
            ttl.import_from_bytes(val)
            self.__update_keyval(key, ttl)
           
       
        r = msg.get_r_identity()
        self.open_messages[f"state-{r}"].mark_done() 
        request_data = self.open_message_data[f"state-{r}"]
        request_data["done"] = True # passes by ref.

    def __mark_use(self, address : bytes):
        if(address + b'/P' not in self.marking_use):
            # impossible! Client connected without saying hello first!
            # drop!
            print("Client connected without saying hello first! Dropping!")
            return False
        if(address + b'/Q' not in self.marking_use):
            # impossible! Client connected without saying hello first!
            # drop!
            print("Client connected without saying hello first! Dropping!")
            return False
        
        pub_q = self.marking_use[address + b'/P']
        if(pub_q not in self.endpoints_kv):
            # client dropped out and came back!
            ttl = IP_TTL()
            ttl.create_owned(pub_q[:-2])
            self.__update_keyval(pub_q, ttl, distribute=True,ownership_connection=True) # connected to me
            ttl = IP_TTL()
            ttl.create_owned(pub_q[:-2])
            self.__update_keyval(pub_q,  ttl, distribute=True, ownership_connection=True) # connected to me
        else:
            # normal. 
            v = self.endpoints_kv[pub_q].mark_use()
            if(v):
                self.__post_update(pub_q, self.endpoints_kv[pub_q],distribute=True) # force on dealer socket too.
        
        query_q = self.marking_use[address + b'/Q']
        if(query_q not in self.endpoints_kv):
            # client dropped out and came back!
            ttl = IP_TTL()
            ttl.create_owned(query_q[:-2])
            self.__update_keyval(query_q, ttl, distribute=True,ownership_connection=True) # connected to me
            ttl = IP_TTL()
            ttl.create_owned(query_q[:-2])
            self.__update_keyval(query_q,  ttl, distribute=True, ownership_connection=True) # connected to me
        else:
            # normal. 
            v = self.endpoints_kv[query_q].mark_use()
            if(v):
                self.__post_update(query_q, self.endpoints_kv[query_q],distribute=True) # force on dealer socket too.
        
        return True

    def __post_update(self, key : str, data : IP_TTL, distribute=False):
        self.new_data = True
        # print(f"Update [{key}] = {data.get_ip_or_null()}")
        pk = PeerKV_Subscribe()  # TODO: Add "repeat-missing" updates!
        pk.create("IP Update")
        pk.set_key(key)
        pk.set_value(self.endpoints_kv[key].prep_for_send())
        self.publish_update_socket.send_multipart(pk.compile())

        if(not(distribute)):
            return
        
        # You owned these changes!

        pk = PeerKV()
        r = random.randint(0,32766)
        while f"push-change-{r}" in self.open_messages:  # TODO: Instead of R, do hash of data.
            r = random.randint(0,32766)

        pk.push_change(key, self.endpoints_kv[key].prep_for_send(), r)
        rm = self.peer_query_socket_RE.add_message(pk.compile(), 5, 2)
        self.open_message_data[f"push-change-{r}"] = {"done" : False}
        self.open_messages[f"push-change-{r}"] = rm
    
        # wait for it to be done! (Makes it blocking now TODO: Design Decision!)
        # while not(self.open_message_data[f"push-change-{r}"]["done"]):
        #     time.sleep(1) # try every 10 msec
        #     print('Blocked')


    def __update_keyval(self, key : str, val : IP_TTL, distribute=False, ownership_connection=False):
        # push changes. Ownership is if you made it.
        ip = val.get_ip_or_null()
        if(ip is None):
            return

        changed = False
        if(ownership_connection):
            # new connection.
            if(key in self.endpoints_kv):
                old = self.endpoints_kv[key]
                p = old.prep_for_send()
                ttl = IP_TTL()
                ttl.create_owned(ip)
                ttl.import_from_bytes(p)
                changed = ttl.process_incoming(val)
                self.endpoints_kv[key] = ttl
            else:
                # first time never before heard!
                ttl = IP_TTL()
                ttl.create_owned(ip)
                ttl.process_incoming(val)
                changed = True
                self.endpoints_kv[key] = ttl
        else:
            if(key in self.endpoints_kv):
                # already exist.
                changed = self.endpoints_kv[key].process_incoming(val)
            else:
                # does not exist. New peer added somewhere
                ttl = IP_TTL()
                ttl.create(ip,val.get_ttl())
                ttl.import_from_bytes(val.prep_for_send())
                self.endpoints_kv[key] = ttl

        if(not(changed)):
            return
        # print(f"Pushed changes! - {key} - {datetime.datetime.fromtimestamp(val.get_ttl())} - {ownership_connection}")
        self.__post_update(key, self.endpoints_kv[key], distribute=distribute)
        self.prune_endpoints()


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
        endpt_pub = endpoints[0]
        endpt_query = endpoints[1] # TODO: Currently does not save if passed in TTL is 0

        ttl = IP_TTL()
        ttl.create_owned(endpt_pub[:-2])
        self.__update_keyval(endpt_pub, ttl, distribute=True,ownership_connection=True) # connected to me
        ttl = IP_TTL()
        ttl.create_owned(endpt_query[:-2])
        self.__update_keyval(endpt_query,  ttl, distribute=True, ownership_connection=True) # connected to me

        # store address/ip in lookup table for mark use
        self.marking_use[address + b'/P'] = endpt_pub
        self.marking_use[address + b'/Q'] = endpt_query

        # doesn't matter for retries.
        pk_response = PeerKV_Hello()
        pk_response.create(
                   msg.get_r_identity(), 
                   self.serving_endpoint_pub + "/P",
                   self.serving_endpoint_query + "/Q",
                   )
        pk_response.set_welcome()

        self.receive_query_socket.send_multipart(
            pk_response.compile_with_address(address))

    def __subscribed_updates(self, msg : PeerKV_Subscribe):
        key = msg.get_key()        
        v = IP_TTL()
        v.import_from_bytes(msg.get_value())
        self.__update_keyval(key,  v)
    
    def __answer_state_request(self, msg : PeerKV, address : bytes):
        
        test = self.__mark_use(address)
        if(not(test)):
            pk_response = PeerKV()
            pk_response.error_feedback(10,"return_state",msg.get_r_identity())
            self.receive_query_socket.send_multipart(
                pk_response.compile_with_address(address))
            return
                
        self.prune_endpoints()
        pk_response = PeerKV()
        results = []
        for val in self.endpoints_kv:
            results.append((val, self.endpoints_kv[val].prep_for_send()))

        pk_response.return_state_receipt(results, msg.get_r_identity())
        self.receive_query_socket.send_multipart(
            pk_response.compile_with_address(address))
    
    def __answer_pushed_change(self, msg : PeerKV, address : bytes):
        
        test = self.__mark_use(address)
        if(not(test)):
            pk_response = PeerKV()
            pk_response.error_feedback(10,"push_change_receive",msg.get_r_identity())
            self.receive_query_socket.send_multipart(
                pk_response.compile_with_address(address))
            return

        
        pk_response = PeerKV()
        key, val_raw = msg.get_push_key_val()

        v = IP_TTL()
        try:
            v.import_from_bytes(val_raw)
        except Exception as e:
            dump(msg.compile_with_address(address))
            raise e
        self.__update_keyval(key,  v)
        
        pk_response.return_push_change(msg.get_r_identity())

        self.receive_query_socket.send_multipart(
            pk_response.compile_with_address(address))
    
    def __receive_dummy(self, msg : BasicMultipartMessage, address : bytes):
        test = self.__mark_use(address)
        if(not(test)):
            pk_response = PeerKV()
            pk_response.error_feedback(10,"dummy",0)
            self.receive_query_socket.send_multipart(
                pk_response.compile_with_address(address))
            return
        
        #print("Dummy")

        # do nothing.

    # to be run by a thread!
    def handle_responses(self,status_socket : zmq.Socket):
        poller = zmq.Poller() # put number in here if you want a timeout
        poller.register(self.receive_query_socket, zmq.POLLIN)
        poller.register(self.peer_subscribe_socket, zmq.POLLIN)
        poller.register(self.peer_query_socket_incoming, zmq.POLLIN)
        poller.register(status_socket, zmq.POLLIN)

        while True:
            socket_receiving = dict(poller.poll(5000))
            if(status_socket in socket_receiving):
                msg = status_socket.recv_string()
                if(msg == "STOP"):
                    break

            self.prune_endpoints()

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
                    
                elif(data[0] == b'dummy'):
                    pk = BasicMultipartMessage()
                    pk.import_msg(data)
                    self.__receive_dummy(pk,addr)

                else:
                    raise ValueError("Unknown message received from Query Router Socket")
            
            if(self.peer_query_socket_incoming in socket_receiving):
                msg = self.peer_query_socket_incoming.recv_multipart()
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
                    elif(pk.is_error_msg()):
                        error, cmd = pk.get_error_code()
                        if(error == 10):
                            # Must reconnect to server, I must have dropped or previously connected
                            # resend a hello
                            print("Failed command: ", cmd)

                            r = random.randint(0,32766)
                            while f"hello-{r}" in self.open_messages:  # TODO: Instead of R, do hash of data.
                                r = random.randint(0,32766)

                            self.open_message_data[f"hello-{r}"] = {"done" : False,"next-state":True}
                            self.__send_hello(r)
                            # wait for the RE to then request it again.
                    else:
                        raise ValueError("Unknown message received from Peer Dealer Socket")

                else:
                    raise ValueError("Unknown message received from Peer Dealer Socket")
            
    





        
