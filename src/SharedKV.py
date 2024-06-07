
import binascii
import os
import threading
import time
import zmq

from MessageFormats import PeerKV, PeerKV_Hello, PeerKV_Hello_Receipt, dump


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

        self.keyvalues = {} # IP is key. TTL is value.

        self.control_socket_outside, inside_socket = zpipe(self.context)

        self.th = threading.Thread(None,self.handle_responses,args=(inside_socket,),name="KeyVal Management")
        self.th.start()

        self.ticker = {}
        self.ticker["connect-peer"] = -1


    def connect_to_peer(self, endpoint_publish_point, endpoint_query):
        self.peer_subscribe_socket.connect(endpoint_publish_point)
        self.peer_query_socket.connect(endpoint_query)
    
        self.send_hello()
       
    def send_hello(self):
         # Currently, this will be sent to ALL connected peers (dealer socket)
        msg = PeerKV_Hello()
        msg.create(self.serving_endpoint_pub,
                   self.serving_endpoint_query,
                   self.ttl + time.time()
                   )
        self.peer_query_socket.send_multipart(msg.compile())
        print("Sent hello!")
        self.ticker["connect-peer"] = time.time() + 10 # 10 sec timeout!

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
                    self.peers[f"{identity}-pub"] = endpoints[0]
                    self.peers[f"{identity}-query"] = endpoints[1]

                    pk_response = PeerKV_Hello_Receipt()
                    pk_response.create()
                    self.receive_query_socket.send_multipart(
                        pk_response.compile_with_address(identity))
                    print('Sent response to hello!', time.time())          

                elif(data[0] == b'General'):
                    pk = PeerKV()
                    pk.import_msg(msg)

                else:
                    raise ValueError("Unknown message received from Query Router Socket")
            
            if(self.peer_query_socket in socket_receiving):
                msg = self.peer_query_socket.recv_multipart()

                if(msg[0] == b'Welcome'):
                    pk = PeerKV_Hello_Receipt()
                    pk.import_msg(msg)
                    self.ticker["connect-peer"] = 0 # done!      
                    print("Connected!")  
                else:
                    raise ValueError("Unknown message received from Peer Dealer Socket")
            
            if(self.ticker["connect-peer"] > 100 and self.ticker["connect-peer"] < time.time()):
                # resend hello!
                print("Resending Hello!")             
                self.send_hello()
            

    





        
