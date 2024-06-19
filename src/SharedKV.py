
import binascii
import datetime
import os
import threading
import time
from typing import Dict, List, Set, Union
import zmq

from MessageFormats import *
from ReliabilityEngine import *
from ttl import IP_TTL, DataTTL_Handler, DataWithTTL

DEFAULT_TTL = 20
IDENTITY_TTL = 86400

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

IP_KEY = ">ip>"
IDENTITY_KEY = ">id_graph>"

def kv_key(root, key):
    return root + str(key)

class KeyValueCommunications():
    def __init__(self, serving_endpoint_query, my_identity):
        
        self.context = zmq.Context()
        self.my_identity = my_identity
        self.serving_endpoint_query = serving_endpoint_query
        # self.ttl = 60 + time.time() # TODO: Implement heart beating and real TTLs.
        # sockets for binding to receive connections from peers
                
        self.receive_query_socket = self.context.socket(zmq.ROUTER)
        self.receive_query_socket.bind(serving_endpoint_query)

        # # self.peer_subscribe_socket.setsockopt(zmq.IDENTITY,my_identity)

        # TODO: Design Decision: Dealer sends communications to ALL connected peers

        # TODO: Identity is not required here. (Key Value doesn't have identity.)

        # self.endpoints_kv : Dict[str, DataWithTTL] = {} # IP is key. TTL is value.
        self.endpoints_kv : DataTTL_Handler = DataTTL_Handler(self.__send_update)

        self.connected_peers : Set[str] = set() # outbound connections!
        self.connected_sockets : Dict[str, Dict[str, Union[ReliabilityEngine | zmq.Socket]]] = {} # outbound connections!

        self.inbound_peers : Dict[str, bytes] = {} # inbound connections!
        self.inbound_peers_addr = {}

        self.new_data = False
        # do not add yourself, others will tell you the TTL.

        self.control_socket_outside, inside_socket = zpipe(self.context)

        self.open_messages : Dict[str, ReliableMessage] = {}
        self.open_message_data : Dict[str, any] = {}

        self.th = threading.Thread(None,self.handle_responses,args=(inside_socket,),name="KeyVal Management")
        self.th.start()

        base = kv_key(IDENTITY_KEY,self.my_identity)
        self.set(base,f"{self.my_identity} + LIMIT",ttl=IDENTITY_TTL + time.time())

    def printf(self, msg, end='\n'):
        colors = {101:93, 102:137, 103: 75, 104: 28, 105: 168, 106:106, 107:107, 108:108,109:109,110:110}
        color_print = f"\033[38;5;{colors[self.my_identity]}m"
        color_stop = "\033[0m"
        print(f"{color_print}Node {self.my_identity} | {datetime.datetime.now()} : {msg}{color_stop}",end = end)

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

    def connect_to_peer(self, endpoint_query, block=True):

        if(f"{endpoint_query}" in self.connected_peers):
            self.printf("Already connected to Peer! Aborting")
            return
    
        socket = self.context.socket(zmq.DEALER)
        socket.setsockopt(zmq.IDENTITY,str(self.my_identity).encode("utf-8")) # TODO: Set ID as key.
        output, b = zpipe(self.context)
        self.connected_sockets[endpoint_query] = {"re" : ReliabilityEngine(self.context, socket, b)}
        self.connected_sockets[endpoint_query]["out"] = output
        self.connected_sockets[endpoint_query]["last_seen"] = 0
        self.connected_sockets[endpoint_query]["avg"] = DEFAULT_TTL
        self.printf(f"Connect { self.connected_sockets[endpoint_query]['out']}")
        self.control_socket_outside.send_multipart([b'connect',endpoint_query.encode('utf-8')])

        i = self.connected_sockets[endpoint_query]["re"].get_number_peers()
        i2 = i
        self.connected_sockets[endpoint_query]["re"].add_peer(endpoint_query)
        while(i == i2): # wait for connect.
            i2 = self.connected_sockets[endpoint_query]["re"].get_number_peers()
            time.sleep(0.001)

        # connected! Send hello!
        reply_id = self.__send_hello(endpoint_query, not(block))
        
        # wait for it to be done!
        while not(self.open_message_data[f"hello-{reply_id}"]["done"]):
            if(not(block)):
                break
            time.sleep(0.01) # try every 10 msec
        
        if(not(block)):
            return
        
        reply_id = self.__send_state_request(endpoint_query)

        # wait for it to be done!
        while not(self.open_message_data[f"state-{reply_id}"]["done"]):
            time.sleep(0.01) # try every 10 msec
        
        reply_id = self.__send_request_connection(endpoint_query)

        # wait for it to be done!
        while not(self.open_message_data[f"send-request-{reply_id}"]["done"]):
            time.sleep(0.01) # try every 10 msec

    def get_endpoints(self):
        return self.endpoints_kv

    def disconnect_from_peer(self, endpoint_query, skip=False):
        if(endpoint_query not in self.connected_peers):
            self.printf(f"Error - already disconnected from {endpoint_query}")
            return
        if(not(skip)):
            self.__send_disconnect_request(endpoint_query)
            time.sleep(0.1)
        self.connected_peers.remove(endpoint_query)
        self.connected_sockets[endpoint_query]["re"].remove_peer(endpoint_query)
        self.control_socket_outside.send_multipart([b'disconnect',endpoint_query.encode('utf-8')])
        self.printf(f"Disconnected from {endpoint_query}")
            

    def stop(self):
        for peer in list(self.connected_peers):
            self.disconnect_from_peer(peer, True)
        self.control_socket_outside.send_multipart([b"STOP"])
        self.th.join()
    
    def endpoints_modified(self):
        i = self.new_data
        return i
    
    def reset_modify(self):
        self.new_data = False

    def pretty_print_endpoint_kv(self, title="Endpoints:"):
        out_debug = title + "\n"
        out_debug += "\t Key \t\t | \t IP-val \t\t\t | \t EXP \t \n"
        self.printf(out_debug)
        for x in self.endpoints_kv.get_keys():
            print(x, end=' | ')

            endpt : DataWithTTL = self.endpoints_kv.get_data(x)

            print(f"{endpt.get_value_or_null()} | "
            f"{datetime.datetime.fromtimestamp(endpt.get_timeout())}   | ")


    
    def string_print_endpoint_kv(self, title="Endpoints:"):
        out_debug = title + "\n"
        out_debug += "\t IP \t\t\t | \t IP-val \t\t\t | \t EXP \t \n"
        for x in self.endpoints_kv.get_keys():
            out_debug += f"{x} | "
            endpt : DataWithTTL = self.endpoints_kv.get_data(x)
            out_debug += f"{endpt.get_value_or_null()} | {datetime.datetime.fromtimestamp(endpt.get_timeout())}   | \n"
        
        return out_debug
        

    def set(self, key, val, ttl=None):
        # I now know endpoint!
        if(ttl is None):
            ttl = DEFAULT_TTL+time.time()
        d = DataWithTTL(val, ttl)
        self.endpoints_kv.merge(key,d)

    def get(self, key):
        return self.endpoints_kv.get_data(key)
    
    def has(self, key):
        return self.endpoints_kv.has(key)
    
    def get_keys(self):
        return self.endpoints_kv.get_keys()


    # Protocol Methods -------------------------------- No blocking allowed in all finishes.
    # All finishes too must be idempotent (assume req's are replayed)


    def __send_hello(self, endpoint, auto_state=False):
        
        reply_id = random.randint(0,32766)
        while f"hello-{reply_id }" in self.open_messages:  # TODO: Instead of R, do hash of data.
            reply_id = random.randint(0,32766)

        self.open_message_data[f"hello-{reply_id }"] = {"query": endpoint,"done" : False}
        if(auto_state):
            self.open_message_data[f"hello-{reply_id}"]["next-state"] = True
         # TODO: Design Decision. Currently, this will be sent to ALL connected peers (dealer socket)
        msg = PeerKV_Hello()
        
        msg.create(
                   reply_id, 
                   self.serving_endpoint_query
                   )
        self.printf(f"Sending hello message with r:{reply_id}") # TODO. DEALER socket distributes requests... this means that it must be repeated.
        
        rm = self.connected_sockets[endpoint]["re"].add_message(msg.compile(),10, 25)
        self.open_messages[f"hello-{reply_id}"] = rm
        return reply_id
    
    
    def __receiving_hello(self, msg : PeerKV_Hello, address : bytes):

        # store address/ip in lookup table for mark use
        endpoint = msg.get_endpoint()
        
        # I now know endpoint!
        self.set(kv_key(IP_KEY,endpoint),f"a{time.time()}")

        # doesn't matter for retries.
        pk_response = PeerKV_Hello()
        pk_response.create_welcome(
                   msg.get_r_identity()
                   )
    
        base = kv_key(IDENTITY_KEY,self.my_identity)
        self.set(base,f"{self.my_identity} + LIMIT",ttl=IDENTITY_TTL + time.time())
        self.set(kv_key(base + ">",address.decode("utf-8")),address.decode("utf-8") + " LAT")

        self.inbound_peers[endpoint] = {"last_seen" : time.time(), "avg" : DEFAULT_TTL, "addr": address, "endpt": endpoint}
        self.inbound_peers_addr[address] = self.inbound_peers[endpoint]

        self.printf(f"Received hello with r:{msg.get_r_identity()}, now I know ID: {endpoint}")
        self.printf(f"Send hello response to PEER with r:{pk_response.get_r_identity()}")
        self.receive_query_socket.send_multipart(
            pk_response.compile_with_address(address))
        

    def __finish_hello(self, msg : PeerKV_Hello):
        r = msg.get_r_identity()
        if(self.open_messages[f"hello-{r}"].is_complete()):
            return # don't need to answer. Already received response
        self.open_messages[f"hello-{r}"].mark_done() 
        request_data = self.open_message_data[f"hello-{r}"]
        endpoint = request_data["query"]

        self.connected_sockets[endpoint]["last_seen"] = time.time()
        self.connected_peers.add(endpoint)

        self.printf(f"Finished Hello. Recv'ed response with r:{msg.get_r_identity()}")

        request_data["done"] = True # passes by ref.
        if("next-state" in request_data):
            self.__send_state_request(endpoint)

    def __send_state_request(self, endpoint):

        reply_id = random.randint(0,32766)
        while f"state-{reply_id }" in self.open_messages:  # TODO: Instead of R, do hash of data.
            reply_id = random.randint(0,32766)

        self.open_message_data[f"state-{reply_id}"] = {"done" : False}
        pk = PeerKV()
        pk.fetch_state_command(r_identity=reply_id)
        self.printf(f"Send State Request r:{endpoint}")
        rm = self.connected_sockets[endpoint]['re'].add_message(pk.compile(), 10, 5) 
        self.open_messages[f"state-{reply_id}"] = rm
        return reply_id
    
    def __receive_state_request(self, msg : PeerKV, address : bytes):
        self.printf(f"Received State Request r:{msg.get_r_identity()}")

        pk_response = PeerKV()
        results = []
        self.printf("Sending: ")
        for key in self.endpoints_kv.get_keys(): # general. Transfer all keys
            dat = self.endpoints_kv.get_data(key)
            v = dat.get_value_or_null()
            if(v is not None):
                results.append((key, dat))
                print(key, ":", v, datetime.datetime.fromtimestamp(dat.get_timeout()))

        self.printf(f"Send State Response to PEER r:{msg.get_r_identity()}")
        pk_response.return_state_receipt(results, msg.get_r_identity())
        self.receive_query_socket.send_multipart(
            pk_response.compile_with_address(address))
    
    def __finish_state_request(self, msg: PeerKV):
        state = msg.get_state_from_return()
        if(self.open_messages[f"state-{msg.get_r_identity()}"].is_complete()):
            self.printf(f"Finish State Req - message already received. Drop r:{msg.get_r_identity()}")
            return # don't need to answer. Already received response due to dealer.
        
        # merge the key values together.
        self.printf("Received: ")
        for state_val in state:
            key = state_val[0]
            val = state_val[1]
            print(key,":", val.get_value_or_null(), datetime.datetime.fromtimestamp(val.get_timeout()))
            self.endpoints_kv.merge(key, val)
            
        self.printf(f"Finish State Req. Recv'd response :{msg.get_r_identity()}")
        r = msg.get_r_identity()
        self.open_messages[f"state-{r}"].mark_done() 
        request_data = self.open_message_data[f"state-{r}"]
        request_data["done"] = True # passes by ref.

    def __send_request_connection(self, endpoint):
        reply_id = random.randint(0,32766)
        while f"send-request-{reply_id}" in self.open_messages:  # TODO: Instead of R, do hash of data.
            reply_id = random.randint(0,32766)

        self.printf(f"Sending a connection request to {endpoint} with r:{reply_id}")
        self.open_message_data[f"send-request-{reply_id}"] = {"done" : False}
        pk = PeerKV()
        pk.request_connection_cmd(reply_id)
        rm = self.connected_sockets[endpoint]['re'].add_message(pk.compile(), 10, 5) 
        self.open_messages[f"send-request-{reply_id}"] = rm
        return reply_id
    
    
    def __receive_request_for_connection(self, msg : PeerKV, address : bytes):
        reply_identity = msg.get_r_identity()
        endpoint = self.inbound_peers_addr[address]["endpt"]
        self.printf(f"Received a connection request from {endpoint} with r:{reply_identity}")

        pk = PeerKV()
        self.printf(f"Send response to connection request from {endpoint} with r:{reply_identity}")
        pk.request_connection_feedback(reply_identity)
        self.receive_query_socket.send_multipart(
            pk.compile_with_address(address))
    
        # connect to peer! Will take a second.... (async)
        self.connect_to_peer(endpoint,False)
    
    def __send_disconnect_request(self, endpoint):
        reply_id = random.randint(0,32766)
        while f"disconn-send-request-{reply_id}" in self.open_messages:  # TODO: Instead of R, do hash of data.
            reply_id = random.randint(0,32766)

        self.printf(f"Sending a disconnection request to {endpoint} with r:{reply_id}")
        self.open_message_data[f"disconn-send-request-{reply_id}"] = {"done" : False}
        pk = PeerKV()
        pk.request_disconnect(reply_id)
        rm = self.connected_sockets[endpoint]['re'].add_message(pk.compile(), 0.1, 5) 
        self.open_messages[f"disconn-send-request-{reply_id}"] = rm
        return reply_id
    
    def __receive_disconnect_request(self, msg : PeerKV, addr : bytes):
        endpoint = self.inbound_peers_addr[addr]["endpt"]
        self.printf(f"Received a disconnection request from {endpoint} with r:{msg.get_r_identity()}")
        self.disconnect_from_peer(endpoint, skip=True)
        del self.inbound_peers_addr[addr]


    def __finish_request_for_connection(self, msg : PeerKV):
        r = msg.get_r_identity()
        if(self.open_messages[f"send-request-{r}"].is_complete()):
            return # don't need to answer. Already received response
        self.open_messages[f"send-request-{r}"].mark_done() 
        request_data = self.open_message_data[f"send-request-{r}"]

        self.printf(f"Finished Request for connection. Recv'ed response with r:{msg.get_r_identity()}")

        request_data["done"] = True # passes by ref.

    def __is_alive(self, endpoint : str, address = None, dealer = False): # outbound means from dealer
        # update endpoint's TTL with new value.

        if(dealer and endpoint not in self.connected_peers):
            self.printf("Isalive: Dealer got feedback while dealer never said hello!")
            return False
        
        if(not(dealer) and endpoint not in self.inbound_peers):
            self.printf("Isalive: Client connected without saying hello first!")
            return False
    
        if(not(dealer) and address is None):
            raise ValueError("Require Address")

        self.printf("Running is alive")

        ttl = DEFAULT_TTL + time.time()
        if(dealer):
            last_seen = self.connected_sockets[endpoint]["last_seen"] 
            avg = self.connected_sockets[endpoint]["avg"]
            avg = (avg * 0.30) + (time.time() - last_seen) * 0.70

            self.printf(f"D - Last seen for {endpoint}: {datetime.datetime.fromtimestamp(last_seen)}")
            self.printf(f"D - Avg for {endpoint}: {avg}")
            self.connected_sockets[endpoint]["last_seen"] = time.time()
            self.connected_sockets[endpoint]["avg"] = avg
        
            a = 0
            if(avg > 3600):
                a = 3600
            else:
                a = avg

            multiplier = 60 * pow(2,-0.2 * avg) + 1.25
            
            ttl = time.time() + a * multiplier
        
            if(ttl - time.time() > 86400):
                ttl = time.time() + 86400
            elif(ttl - time.time() < 1):
                ttl = time.time() + 2
            self.printf(f"Calc for ttl: {datetime.datetime.fromtimestamp(ttl)}")
        
        else:
            last_seen = self.inbound_peers[endpoint]["last_seen"] 
            avg = self.inbound_peers[endpoint]["avg"]
            self.printf(f"R - Last seen for {endpoint}: {datetime.datetime.fromtimestamp(last_seen)}")
            self.printf(f"R - Avg for {endpoint}: {avg}")
            avg = (avg * 0.80) + (time.time() - last_seen) * 0.20

            self.inbound_peers[endpoint]["last_seen"] = time.time()
            self.inbound_peers[endpoint]["avg"] = avg
        
            a = 0
            if(avg > 3600):
                a = 3600
            else:
                a = avg

            multiplier = 70 * pow(2,-0.2 * avg) + 2
            
            ttl = time.time() + a * multiplier
        
            if(ttl - time.time() > 86400):
                ttl = time.time() + 86400
            elif(ttl - time.time() < 1):
                ttl = time.time() + 2
            self.printf(f"Calc for ttl: {datetime.datetime.fromtimestamp(ttl)}")
            
            base = kv_key(IDENTITY_KEY,self.my_identity)
            self.set(base,f"{self.my_identity} + LIMIT",ttl=IDENTITY_TTL + time.time())
            self.set(kv_key(base + ">",address.decode("utf-8")),address.decode("utf-8") + " LAT",ttl=int(ttl)-1)

        self.set(kv_key(IP_KEY,endpoint),f"abc{time.time()}",ttl)
        self.printf("Finish keep alive")

    
    def __send_update(self, key : str, data : DataWithTTL):
        for peer in self.connected_peers:
            reply_id = random.randint(0,32766)
            while f"update-{reply_id }" in self.open_messages:  # TODO: Instead of R, do hash of data.
                reply_id = random.randint(0,32766)

            msg = PeerKV()
            msg.push_change(key, data, reply_id)
            self.printf(f"Post update r:{reply_id} of [{key}]={data.get_value_or_null()} Timeout: {datetime.datetime.fromtimestamp(data.get_timeout())}- send to {peer}")
            

            rm = self.connected_sockets[peer]["re"].add_message(msg.compile())    
            self.open_messages[f"update-{reply_id}"] = rm
            
    def __receive_update(self, msg : PeerKV, address : bytes):
            
        pk_response = PeerKV()
        key, val = msg.get_push_key_val()
       
        self.printf(f"Recv Update By Push - key:{key} r:{msg.get_r_identity()}")
        
        self.endpoints_kv.merge(key, val)
        self.printf(f"Send Update ACK - key:{key} with r:{msg.get_r_identity()}")
        
        pk_response.return_push_change(msg.get_r_identity())

        self.receive_query_socket.send_multipart(
            pk_response.compile_with_address(address))

    def __finish_update(self, msg : PeerKV):
        r = msg.get_r_identity()
        if(self.open_messages[f"update-{r}"].is_complete()):
            self.printf(f"Recv ACK on Push Change r:{r} - duplicate")
            return # don't need to answer. Already received response due to dealer.
        
        self.printf(f"Recv ACK on Push Change r:{r}")
        self.open_messages[f"update-{r}"].mark_done() 

    # Receiving methods ----------------------- No blocking allowed!

    def send_dummy_command(self, command, endpoint):
        msg = BasicMultipartMessage()
        msg.set_val(command)
        
        self.connected_sockets[endpoint]["re"].add_message(msg.compile(), 0, 1)
    
    def __receive_dummy(self, msg : BasicMultipartMessage, address : bytes):
        self.printf(f"Recv dummy command {msg.get_val()}")

    def send_dummy_data(self, data, endpoint):
        addr = self.inbound_peers[endpoint]["addr"]
        msg = BasicMultipartMessage()
        msg.set_val(data)
        lst = msg.compile_with_address(addr)
        lst.insert(0,b'R-Relay') 
        self.control_socket_outside.send_multipart(lst)

    def __receive_dummy_data(self, msg : BasicMultipartMessage):
        self.printf(f"Received dummy data! {msg.get_val()}")


        # msg
        #print("Dummy")

        # do nothing.

    # to be run by a thread!
    def handle_responses(self,status_socket : zmq.Socket):
        poller = zmq.Poller() # put number in here if you want a timeout
        poller.register(self.receive_query_socket, zmq.POLLIN)
        poller.register(status_socket, zmq.POLLIN)

        while True:
            socket_receiving = dict(poller.poll(5000))
            if(status_socket in socket_receiving):
                msg = status_socket.recv_multipart()
                if(msg[0] == b"STOP"):
                    break
                if(msg[0] == b'connect'):
                    endpt = msg[1].decode('utf-8')
                    poller.register(self.connected_sockets[endpt]["out"], zmq.POLLIN)
                if(msg[0] == b'disconnect'):
                    endpt = msg[1].decode('utf-8')
                    poller.unregister(self.connected_sockets[endpt]["out"])
                if(msg[0] == b'R-Relay'):
                    dat = msg[1:]
                    self.receive_query_socket.send_multipart(dat)

            # prune
            # for endpoint in list(self.endpoints_kv.get_keys()):
            #     if(self.endpoints_kv.get_data(endpoint).get_value_or_null() is None):
            #         self.printf("Pizza")
            #         if(endpoint in self.connected_peers):
            #             self.printf(f"Peer {endpoint} disconnected (expired)!")
            #             # same as remove peer thread
            #             self.connected_sockets[endpoint]["out"].remove_peer_listen_thread(endpoint)
            #             self.connected_sockets[endpoint]["out"].send_multipart([b"RE ENGINE disconnect",endpoint.encode('utf-8')])
            #             poller.unregister(self.connected_sockets[endpoint]["out"])
            #             self.connected_peers.remove(endpoint)
            #         self.endpoints_kv.del_key(endpoint)
            #         self.new_data = True

            if(self.receive_query_socket in socket_receiving):

                msg = self.receive_query_socket.recv_multipart()
                addr = msg[0]
                data = msg[1:]

                # self.printf("Received on router")
                # dump(msg)
                # self.printf("---")
                if(addr not in self.inbound_peers_addr):
                    if(data[0] == b'Hello!'):
                        # good. new peer. hello
                        pk = PeerKV_Hello()
                        pk.import_msg(data)
                        self.__receiving_hello(pk, addr)
                    else:
                        self.printf("New peer did not say hello! Dropping")
                    
                    continue

                peer = self.inbound_peers_addr[addr]["endpt"]
                self.__is_alive(peer, address=addr)
                
                if(data[0] == b'General'):
                    pk = PeerKV()
                    pk.import_msg(data)
                    if(pk.is_fetch_state()):
                        self.__receive_state_request(pk, addr)
                    elif(pk.is_requesting_connection()):
                        self.__receive_request_for_connection(pk, addr)
                    elif(pk.is_push_change()):
                        self.__receive_update(pk, addr) 
                    elif(pk.is_requesting_disconnection()):
                        self.__receive_disconnect_request(pk, addr)
                    else:
                        raise ValueError("Unknown message received from Query Router Socket")
                elif(data[0] == b'dummy'):
                    pk = BasicMultipartMessage()
                    pk.import_msg(data)
                    self.__receive_dummy(pk, addr) 
                else:
                    raise ValueError("Unknown message received from Query Router Socket")
            
            for peer in self.connected_sockets:
                socket = self.connected_sockets[peer]["out"]
                if(not(socket) in socket_receiving):
                    continue

                msg = socket.recv_multipart()

                # self.printf("Received on dealer")
                # dump(msg)
                # self.printf("---")

                if(msg[0] == b'Welcome'):
                    pk = PeerKV_Hello()
                    pk.import_msg(msg)
                    self.__finish_hello(pk)
                
                elif(msg[0] == b'General'):
                    self.__is_alive(peer,dealer=True)
                    pk = PeerKV()
                    pk.import_msg(msg)
                    if(pk.is_return_state()):
                        self.__finish_state_request(pk)
                    elif(pk.is_push_change_receive()):
                        self.__finish_update(pk)
                    elif(pk.is_requesting_connection_feedback()):
                        self.__finish_request_for_connection(pk)
                    elif(pk.is_error_msg()):
                        error, cmd = pk.get_error_code()
                        if(error == 10):
                            # Must reconnect to server, I must have dropped or previously connected
                            # resend a hello
                            self.printf(f"Failed command: {cmd}")
                            self.__send_hello(peer)
                            # wait for the RE to then request it again.
                    else:
                        raise ValueError("Unknown message received from Peer Dealer Socket")

                elif(msg[0] == b'dummy'):
                    self.__is_alive(peer,dealer=True)
                    pk = BasicMultipartMessage()
                    pk.import_msg(data)
                    self.__receive_dummy_data(pk) 

                else:
                    raise ValueError("Unknown message received from Peer Dealer Socket")
            
    





        
