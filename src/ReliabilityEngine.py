


import binascii
import os
import random
import threading
from typing import List
import time

import zmq
import pickle
import string

def dump(msg):
    for part in msg:
        print("[%03d]" % len(part), end=' ')        
        try:
            s_raw = part.decode('ascii')
            for x in s_raw:
                if(x not in string.printable):
                    raise ValueError
            print(s_raw)
        except (UnicodeDecodeError, ValueError) as e:
            print(r"0x %s" % (binascii.hexlify(part, ' ').decode('ascii')))

class ReliableMessage():
    def __init__(self, data, retry_gap, max_retry):
        self.data = data
        self.status = False
        self.retry_gap = retry_gap
        self.max_retry = max_retry

    def mark_done(self):
        self.status = True

    def is_complete(self):
        return self.status


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

class ReliabilityEngine():
    def __init__(self, ctx : zmq.Context, socket : zmq.Socket, output : zmq.Socket) -> None:

        self.timer : List[float] = []
        self.msg_objects : List[ReliableMessage] = []
        self.signal = threading.Event()
        self.signal.clear()
        self.is_stop = False
        self.peers = 0

        self.th = threading.Thread(None,self.replay_management,name="Reliability Engine Thread")
        self.th.start()

        self.control_pipe, pipe = zpipe(ctx)

        self.th2 = threading.Thread(None, self.socket_management, args=(pipe, output, socket), name="Reliablity Socket Thread")
        self.th2.start()

        self.pending_tasks = 0
        self.output_socket = output

        self.verified_peers = 0

    def socket_management(self, pipe : zmq.Socket, output : zmq.Socket, primary : zmq.Socket):
        poller = zmq.Poller()
        poller.register(pipe, zmq.POLLIN)
        poller.register(primary, zmq.POLLIN)

        while True:
            socket_receiving = dict(poller.poll(1000))
            if(pipe in socket_receiving):
                i = pipe.recv_multipart()
                # dump(i)
                # print('-')
                if(i[0] == b"STOP STOP STOP RE ENGINE"):
                    break
                if(i[0] == b"RE ENGINE connect"):
                    # print("Connected")
                    primary.connect(i[1].decode('utf-8'))
                    self.verified_peers += 1
                elif(i[0] == b"RE ENGINE disconnect"):
                    # print("Disconnected")
                    primary.disconnect(i[1].decode('utf-8'))
                    self.verified_peers -= 1

                    if(self.peers > 0):
                        self.peers -= 1
                else:
                    # print("Send: ",i)
                    # for x in range(self.verified_peers): # TODO. DEALER distributes requests
                    primary.send_multipart(i)
                        
            if(primary in socket_receiving):
                i = primary.recv_multipart()
                output.send_multipart(i)

    def get_number_pending(self):
        return self.pending_tasks
    
    def get_number_peers(self):
        return self.verified_peers

    def add_peer(self, endpoint : str):
        # print("connect")
        self.peers += 1
        self.add_message([b"RE ENGINE connect",endpoint.encode('utf-8')],max_retry=1)

    def add_peer_listen_thread(self, endpoint : str):
        # print("connect")
        self.peers += 1
        # self.output_socket.send_multipart([b"RE ENGINE connect",endpoint.encode('utf-8')],max_retry=1)
    
    def remove_peer(self, endpoint : str):
        # print("Disc")
        self.add_message([b"RE ENGINE disconnect",endpoint.encode('utf-8')],max_retry=1)
    

    def __add_to_timer(self,time_fire : float, msg : ReliableMessage):       
        count = 0
        while count < len(self.timer) and self.timer[count] < time_fire:
            count += 1
        
        self.timer.insert(count,time_fire)
        self.msg_objects.insert(count, msg)
        self.signal.set()
        # print("Added to timer")
        # print("QUEUE: ",self.timer)

    def add_message(self, message: List[bytes], retry_gap=10, max_retry=None) -> ReliableMessage:
        if(max_retry is not None and max_retry <= 0):
            return
        if(self.peers == 0):
            return # drop if no one to send to!
        
        # print(f"Sent message: {message}. Time: {time.time() % 240} Remaining: {self.pending_tasks}")
        msg = ReliableMessage(message,retry_gap,max_retry)
        # print("MESSAGE  : ",msg.data)
        self.__add_to_timer(0, msg) # send immediately!
        self.pending_tasks += 1
        
        self.__add_to_timer(retry_gap + time.time(), msg)
        self.pending_tasks += 1
        return msg
    
    def add_message_delay(self, message: List[bytes], delay=1, retry_gap=10, max_retry=None) -> ReliableMessage:
        if(max_retry is not None and max_retry <= 0):
            return
        if(self.peers == 0):
            return # drop if no one to send to!
        
        #print(f"Sent message: {message}. Time: {time.time() % 240} Remaining: {self.pending_tasks}")
        msg = ReliableMessage(message,retry_gap,max_retry)
        # print("MESSAGE  : ",msg.data)
        self.__add_to_timer(time.time() + delay, msg) # send immediately!
        self.pending_tasks += 1
        
        self.__add_to_timer(retry_gap + time.time() + delay, msg)
        self.pending_tasks += 1
        return msg

    def add_message_RM(self, msg: ReliableMessage) -> ReliableMessage:
        # print("RM: ", msg.max_retry)
        if(msg.max_retry is not None and msg.max_retry <= 0):
            return
        if(msg.max_retry is not None):
            msg.max_retry -= 1
        #print('Retry')
        if(self.peers == 0):
            return # drop if no one to send to!
        self.control_pipe.send_multipart(msg.data)
        # print(f"Sent message: {msg.data}. Remain: {self.pending_tasks}")
        self.__add_to_timer(msg.retry_gap + time.time(), msg)
        self.pending_tasks += 1
        return msg

    def stop(self):
        self.is_stop = True
        self.signal.set()
        self.th.join()

    def replay_management(self):
        while True:
            wait_start = time.time()
            if(len(self.timer) == 0):
                self.signal.wait()
            else:
                w = self.timer[0] - time.time()
                if( w > 0):
                    self.signal.wait(w)

            if(self.is_stop):
                self.control_pipe.send_multipart([b"STOP STOP STOP RE ENGINE"])
                break

            wait_end = time.time()
            self.timer[0] = self.timer[0] - (wait_end - wait_start)
            # print(f"Time Remaining: {(time.time() - self.timer[0]) % 240}.")
            # print("MESSAGE-r: ",self.msg_objects[0].data, self.timer[0])
            if(self.timer[0] < time.time()):
                msg = self.msg_objects[0]
                if(not(msg.is_complete())):
                    # print("PIzza@")
                    self.add_message_RM(msg)
                self.timer.pop(0) 
                self.msg_objects.pop(0)
                self.pending_tasks -= 1
            
            self.signal.clear()

            


if __name__ == "__main__":
    re = ReliabilityEngine(None)
    

    re.add_message(f"Hello world!",1,5)
    