


import random
import threading
from typing import List
import time

import zmq
import pickle

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

class ReliabilityEngine():
    def __init__(self, socket : zmq.Socket) -> None:
        
        self.socket = socket

        self.timer : List[float] = []
        self.msg_objects : List[ReliableMessage] = []
        self.signal = threading.Event()
        self.signal.clear()
        self.is_stop = False
        self.peers = 0

        self.th = threading.Thread(None,self.replay_management,name="Reliability Engine Thread")
        self.th.start()

        self.pending_tasks = 0

    def get_number_pending(self):
        return self.pending_tasks

    def add_peer(self):
        self.peers += 1
    
    def remove_peer(self):
        if(self.peers > 0):
            self.peers -= 1

    def __add_to_timer(self,time_fire : float, msg : ReliableMessage):       
        count = 0
        while count < len(self.timer) and self.timer[count] < time_fire:
            count += 1
        
        self.timer.insert(count,time_fire)
        self.msg_objects.insert(count, msg)
        self.signal.set()
        # print("QUEUE LENGTH: ",len(self.timer))

    def add_message(self, message: List[bytes], retry_gap=10, max_retry=None) -> ReliableMessage:
        if(max_retry is not None and max_retry <= 0):
            return
        if(self.peers == 0):
            return # drop if no one to send to!
        self.socket.send_multipart(message)
        #print(f"Sent message: {message}. Time: {time.time() % 240} Remaining: {self.pending_tasks}")
        msg = ReliableMessage(message,retry_gap,max_retry)
        self.__add_to_timer(retry_gap + time.time(), msg)
        # print("MESSAGE: ",msg.data)
        self.pending_tasks += 1
        return msg
    
    def add_message_RM(self, msg: ReliableMessage) -> ReliableMessage:
        if(msg.max_retry is not None and msg.max_retry <= 0):
            return
        if(msg.max_retry is not None):
            msg.max_retry -= 1
        #print('Retry')
        if(self.peers == 0):
            return # drop if no one to send to!
        self.socket.send_multipart(msg.data)
        #print(f"Sent message: {msg.data}. Time: {time.time() % 240} Remaining: {self.pending_tasks}")
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
                break

            wait_end = time.time()
            self.timer[0] = self.timer[0] - (wait_end - wait_start)
            # print(f"Time Remaining: {(time.time() - self.timer[0]) % 240}.")
            if(self.timer[0] < time.time()):
                msg = self.msg_objects[0]
                if(not(msg.is_complete())):
                    self.add_message_RM(msg)
                self.timer.pop(0) 
                self.msg_objects.pop(0)
                self.pending_tasks -= 1
            
            self.signal.clear()

            


if __name__ == "__main__":
    re = ReliabilityEngine(None)
    

    re.add_message(f"Hello world!",1,5)
    