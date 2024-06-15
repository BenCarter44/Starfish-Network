
import datetime
import threading
import time
from typing import Callable, Dict, Optional, Union
import dill

from ReliabilityEngine import ReliabilityEngine

class DataWithTTL():
    pass

class DataWithTTL():
    def __init__(self, data : any, timeout : float, suppress_error : bool = False):
        """Initiate a simple data object with Time-To-Live. Supposed to be immutable.

        Args:
            data (any): Data to store
            timeout (float): timeout in UNIX timestamp.
            suppress_error (bool): Set to true to ignore ValueError on creation

        Raises:
            ValueError: If timeout is in the past, raise ValueError.
        """
        self.__data = data
        self.__timeout = timeout
        self.__time_created = time.time()
        if(not(suppress_error) and self.__timeout < self.__time_created):
            raise ValueError("Timeout in the past!")
    
    def get_value(self) -> any:
        """Get value stored

        Raises:
            ValueError: If past TTL, throw exception.

        Returns:
            any: Data stored.
        """
        if(self.__timeout > time.time()):
            return self.__data
        else:
            raise ValueError("Value Expired!")
    
    def get_timeout(self) -> float:
        """Return the timeout

        Returns:
            float: Timeout in UNIX seconds.
        """
        return self.__timeout

    def is_valid(self) -> bool:
        """Return true if still alive

        Returns:
            bool: True if alive
        """
        return self.__timeout > time.time()

    
    def get_value_or_null(self) -> Optional[any]:
        """Get value stored, or return None if past TTL.

        Returns:
            Optional[any]: Data stored or None if past TTL.
        """
        if(self.__timeout > time.time()):
            return self.__data
        else:
            return None
    
    def to_bytes(self) -> bytes:
        return dill.dumps((self.__data, self.__timeout))

    def get_raw_val(self):
        return self.__data

    def from_bytes(self, byt : bytes):
        byt = dill.loads(byt)
        self.__data = byt[0]
        self.__timeout = byt[1]
        self.__time_created = time.time()
    

class DataTTL_Handler():
    def __init__(self, send_handler : Callable):
        self.data = {}
        self.UPDATE_OFFSET = 5
        self.cache : Dict[str, Optional[DataWithTTL]] = {}
        self.evt = threading.Event()
        self.is_stop = False
        self.th = threading.Thread(None,self.wait_thread)
        self.th.start()
        self.send_msg = send_handler
        self.old_timeouts = {}
    
    def add_data_TTL(self, key : str, data : DataWithTTL):
        self.data[key] = data
        self.cache[key] = None
        self.old_timeouts[key] = time.time()
    
    def get_keys(self):
        return self.data.keys()

    def add_merge_data_TTL(self, key : str, data : DataWithTTL):
        if(key in self.data):
            self.merge(key, data)
        else:
            self.add_data_TTL(key,data)
        
    def del_key(self, key):
        del self.data[key]
        del self.cache[key]
    
    def stop(self):
        self.is_stop = True
        self.evt.set()
        self.th.join()

    def merge(self, key : str, inc : DataWithTTL):
        if(key not in self.data):
            self.add_data_TTL(key, inc)
            self.send_msg(key, self.data[key])
            return True
        
        if(inc.get_timeout() < self.data[key].get_timeout() + 1):
            # force at least one sec update
            return False # drop
        
        # if inc.get_timeout() > self.data[key].get_timeout()

        if(self.data[key].get_timeout() - self.UPDATE_OFFSET > time.time()): # still got time
            if(self.cache[key] is not None):
                r = self.cache[key].get_timeout()
                if(inc.get_timeout() > r):
                    self.cache[key] = inc
                    self.evt.set()
            else:
                self.cache[key] = inc
                self.evt.set()
        
            return False
        
        # else

        if(self.cache[key] is not None and inc.get_timeout() > self.cache[key].get_timeout()):
            # clear cache
            self.cache[key] = None
            self.evt.set()
            self.data[key] = inc
            self.send_msg(key, self.data[key])
            return True
        
        if(self.cache[key] is not None):
            # cache time is greater
            self.data[key] = self.cache[key]
            self.cache[key] = None
            self.evt.set()
            self.send_msg(key, self.data[key])
            return True

        # cache is none
        assert self.cache[key] is None
        self.data[key] = inc
        self.send_msg(key, self.data[key])
        return True

    def wait_thread(self):
        while True:
            self.evt.wait(0.5)
            if(self.is_stop):
                break
            for key in self.cache:
                if(self.cache[key] is not None and
                  self.data[key].get_timeout() - self.UPDATE_OFFSET < time.time()):
                
                    assert self.cache[key].get_timeout() > self.data[key].get_timeout()
                    self.data[key] = self.cache[key]
                    self.send_msg(key, self.data[key]) 
                    self.cache[key] = None


            self.evt.clear()
    
    def get_data(self, key) -> DataWithTTL:
        return self.data[key]

    # def __repr__(self):
    #     val = self.get_value()
    #     valid = self.__timeout > time.time()
    #     if(valid):
    #         return f"{val} - Expires at: {self.__timeout}"
    #     else:
    #         return f"{val} - EXPIRED. Expired at: {self.__timeout}"

class IP_TTL():
    pass
class IP_TTL():

    WINDOW_GATE_THRESHOLD = 0.25
    DEFAULT_TTL = 60

    def __init__(self):
        self.data = None
        self.ttl = 0
        self.last_seen = 0
        self.raw = 0
        self.owned = False
        self.avg_time_send = self.DEFAULT_TTL # self.DEFAULT_TTL seconds per request.

    def create(self, ip, ttl : int):
        self.owned = False
        self.data = ip
        self.ttl = ttl
    
    def create_owned(self, ip, default_rate=None):
        if(default_rate == None):
            default_rate = self.DEFAULT_TTL / 3
        self.owned = True
        self.ttl = self.DEFAULT_TTL + time.time()
        self.last_seen = time.time()
        self.raw = time.time()
        self.data = ip

        self.avg_time_send = default_rate # 10 seconds per request.
        self.__calc_ttl()

    def __calc_ttl(self):        
        a = 0
        if(self.avg_time_send > 3600):
            a = 3600
        else:
            a = self.avg_time_send

        multiplier = 70 * pow(2,-1 * self.avg_time_send) + 30
        
        ttl = self.last_seen + a * multiplier
    
        if(ttl - time.time() > 86400):
            self.ttl = time.time() + 86400
        else:
            self.ttl = ttl

    def prep_for_send(self) -> bytes:
        output = (self.data, self.ttl, self.last_seen, self.owned)
        dat = dill.dumps(output)
        return dat
    
    def import_from_bytes(self, in_data):     
        d = None
        try:   
            d = dill.loads(in_data)
        except dill.UnpicklingError:
            print("DILL ERROR", len(in_data), in_data)
        if d is None:
            print("D NONE ERROR", len(in_data), in_data)
            raise ValueError()
        self.data = d[0]
        self.ttl = d[1]
        self.last_seen = d[2]

    def mark_use(self):
        if(not(self.owned)):
            raise ValueError("Not owned.")
        
        self.avg_time_send = (self.avg_time_send * 0.80) + (time.time() - self.raw) * 0.20 # slowly add 0.05 sec per request. Pushes reliability
        self.raw = time.time()

        window_gate = (self.ttl - self.last_seen) * self.WINDOW_GATE_THRESHOLD + self.last_seen
        if(self.raw <= window_gate):
            return False # drop. Not above gate
        
        self.last_seen = self.raw
    
        self.__calc_ttl()
        
        return True

    def process_incoming(self, incoming : IP_TTL):
        if(incoming.data != self.data):
            raise ValueError("Can't merge when IPs are different")
        
        if(incoming.ttl > self.ttl):
            self.ttl = incoming.ttl
            if(incoming.last_seen > self.last_seen): # TODO: Design Decision: bump last seen too. Check for too many messages
                self.last_seen = incoming.last_seen
            
            if(self.owned):
                self.__calc_ttl()
            
            return True
        
        if(not(self.owned)):
            if(incoming.last_seen > self.last_seen):
                self.last_seen = incoming.last_seen
                return True
            return False

        window_gate = (self.ttl - self.last_seen) * self.WINDOW_GATE_THRESHOLD + self.last_seen
        if(incoming.last_seen <= window_gate):
            return False # drop. Not above gate
        
        self.last_seen = incoming.last_seen
        if(self.owned):
            self.__calc_ttl()
        
        return True

    def get_ip_or_null(self):
        if(time.time() <= self.ttl):
            return self.data
    
    def get_ttl(self):
        return self.ttl
    
    def get_last_seen(self):
        return self.ttl

    def display(self):
        if(not(self.owned)):
            if(self.ttl < time.time()):
                print(f"{self.data} | EXPIRED ({datetime.datetime.fromtimestamp(self.ttl)})| "
                " - \t \t \t | "
                " - \t \t \t | ")
                return True
            print(f"{self.data} | "
                f"{datetime.datetime.fromtimestamp(self.ttl)} | "
                " - \t \t \t | "
                f"{datetime.datetime.fromtimestamp(self.last_seen)} | ")
            return False
    
        window_gate = (self.ttl - self.last_seen) * self.WINDOW_GATE_THRESHOLD + self.last_seen
        if(self.ttl < time.time()):
            print(f"{self.data} |  EXPIRED ({datetime.datetime.fromtimestamp(self.ttl)}) | "
              f"{datetime.datetime.fromtimestamp(self.ttl)}   | "
              f"{datetime.datetime.fromtimestamp(window_gate)}   | "
              f"{datetime.datetime.fromtimestamp(self.last_seen)}   | "
              f"{self.avg_time_send} avg s.")
            return True
        print(f"{self.data} | "
              f"{datetime.datetime.fromtimestamp(self.ttl)} | "
              f"{datetime.datetime.fromtimestamp(window_gate)}   | "
              f"{datetime.datetime.fromtimestamp(self.last_seen)}    | "
              f"{self.avg_time_send} avg s.")
        return False

    def display_string(self):
        if(not(self.owned)):
            if(self.ttl < time.time()):
                return (f"{self.data} | EXPIRED ({datetime.datetime.fromtimestamp(self.ttl)})| "
                " - \t \t \t \t \t \t | "
                " - \t \t \t \t \t \t | ")

            return (f"{self.data} | "
                f"{datetime.datetime.fromtimestamp(self.ttl)} | "
                " - \t \t \t \t \t \t | "
                f"{datetime.datetime.fromtimestamp(self.last_seen)} | ")
    
        window_gate = (self.ttl - self.last_seen) * self.WINDOW_GATE_THRESHOLD + self.last_seen
        if(self.ttl < time.time()):
            return (f"{self.data} |  EXPIRED ({datetime.datetime.fromtimestamp(self.ttl)}) | "
              f"{datetime.datetime.fromtimestamp(self.ttl)}   | "
              f"{datetime.datetime.fromtimestamp(window_gate)}  | "
              f"{datetime.datetime.fromtimestamp(self.last_seen)}  | "
              f"{self.avg_time_send} avg s.")
        return (f"{self.data} | "
              f"{datetime.datetime.fromtimestamp(self.ttl)} | "
              f"{datetime.datetime.fromtimestamp(window_gate)}  | "
              f"{datetime.datetime.fromtimestamp(self.last_seen)} | "
              f"{self.avg_time_send} avg s.")


    

# class HashmapTTL():
#     pass        

# class HashmapTTL():
#     def __init__(self, data : Union[Dict[str, DataWithTTL] | HashmapTTL]):
#         """Either import a dictionary with DataTTL pairs, or another HashmapTTL

#         Args:
#             data (Union[Dict[str, DataWithTTL]  |  HashmapTTL]): Imported data
#         """
#         if(isinstance(data,HashmapTTL)):
#             self.data = data.data 
#         else:
#             self.data = data

#     def get(self, key):
#         if(not(key in self.data)):
#             return None
        
#         val = self.data[key].get_value_or_null()
#         if(val is not None):
#             return val 
    
#     def add(self, key, value, timeout)
    
#     def __getitem__(self, key):
#         return self.get(key)
    
#     def __iter__(self):
#         return self.data
        

# Testing script.

if __name__ == "__main__":
    import random
    network_test = {101:{}, 102:{}, 103:{}, 104:{}, 105:{}}
    network_test[101][101] = IP_TTL()
    network_test[101][101].create(101,0)
    network_test[101][102] = IP_TTL()
    network_test[101][102].create(102,0)
    network_test[101][103] = IP_TTL()
    network_test[101][103].create_owned(103,10)
    network_test[101][104] = IP_TTL()
    network_test[101][104].create(104,0)
    network_test[101][105] = IP_TTL()
    network_test[101][105].create(105,0)
    
    network_test[102][101] = IP_TTL()
    network_test[102][101].create_owned(101,10)
    network_test[102][102] = IP_TTL()
    network_test[102][102].create(102,0)
    network_test[102][103] = IP_TTL()
    network_test[102][103].create(103,0)
    network_test[102][104] = IP_TTL()
    network_test[102][104].create(104,0)
    network_test[102][105] = IP_TTL()
    network_test[102][105].create(105,0)
    
    network_test[103][101] = IP_TTL()
    network_test[103][101].create(101,0)
    network_test[103][102] = IP_TTL()
    network_test[103][102].create_owned(102,10)
    network_test[103][103] = IP_TTL()
    network_test[103][103].create(103,0)
    network_test[103][104] = IP_TTL()
    network_test[103][104].create(104,0)
    network_test[103][105] = IP_TTL()
    network_test[103][105].create_owned(105,10)

    network_test[104][101] = IP_TTL()
    network_test[104][101].create(101,0)
    network_test[104][102] = IP_TTL()
    network_test[104][102].create_owned(102,10)
    network_test[104][103] = IP_TTL()
    network_test[104][103].create(103,0)
    network_test[104][104] = IP_TTL()
    network_test[104][104].create(104,0)
    network_test[104][105] = IP_TTL()
    network_test[104][105].create(105,0)

    network_test[105][101] = IP_TTL()
    network_test[105][101].create(101,0)
    network_test[105][102] = IP_TTL()
    network_test[105][102].create(102,0)
    network_test[105][103] = IP_TTL()
    network_test[105][103].create(103,0)
    network_test[105][104] = IP_TTL()
    network_test[105][104].create_owned(104,10)
    network_test[105][105] = IP_TTL()
    network_test[105][105].create(105,0)

    neighbors = {101:[102], 102:[103,104], 104:[105], 105:[103], 103:[101]}

    k101 = network_test[102][101].prep_for_send()
    k102 = network_test[104][102].prep_for_send()
    k103 = network_test[101][103].prep_for_send()
    k104 = network_test[105][104].prep_for_send()
    k105 = network_test[103][105].prep_for_send()

    network_test[101][101].import_from_bytes(k101)
    network_test[102][102].import_from_bytes(k102)
    network_test[103][103].import_from_bytes(k103)
    network_test[104][104].import_from_bytes(k104)
    network_test[105][105].import_from_bytes(k105)

    network_test[101][102].import_from_bytes(k102)
    network_test[101][104].import_from_bytes(k104)
    network_test[101][105].import_from_bytes(k105)

    network_test[102][103].import_from_bytes(k103)
    network_test[102][104].import_from_bytes(k104)
    network_test[102][105].import_from_bytes(k105)

    network_test[103][101].import_from_bytes(k101)
    network_test[103][104].import_from_bytes(k104)

    network_test[104][101].import_from_bytes(k101)
    network_test[104][103].import_from_bytes(k103)
    network_test[104][105].import_from_bytes(k105)

    network_test[105][101].import_from_bytes(k101)
    network_test[105][102].import_from_bytes(k102)
    network_test[105][103].import_from_bytes(k103)


    def sim_message(to, frm):
        print(f"Node {to} by {frm} sent message")
        return network_test[to][frm].mark_use()    

    def spread(to, frm, dat=None):
        # if(dat is None):
        inc = network_test[to][frm].prep_for_send() # get the data from send
        
        for x in network_test:
            for y in network_test[x]:
                p = IP_TTL()
                p.import_from_bytes(inc)
                print("Packet: ", p.get_ip_or_null())
                if(y != p.get_ip_or_null()):
                    continue
                v = network_test[x][y].process_incoming(p)
                spread(x, y)

        # else:
        #     inc = dat.prep_for_send()
        # for n in neighbors[to]:
        #     print(f"Spreading! From {to} to {n}")
           
        #     rt = sim_message(n, to)
        #     if(rt):
        #         spread(n,to)

        #     p = IP_TTL()
        #     p.import_from_bytes(inc)
        #     print("Packet: ", p.get_ip_or_null())
        #     network_test[n][p.get_ip_or_null()].display()
        #     v = network_test[n][p.get_ip_or_null()].process_incoming(p)
        #     network_test[n][p.get_ip_or_null()].display()
        #     if(v):
        #         spread(n,to,p)

        print("End Spread")

    while True:
        print(f"Current time: {datetime.datetime.now()}")

        frm = random.randint(101,105)
        to = random.choice(neighbors[frm])

        print(f"Sending message from {frm} to {to}")
        updates = sim_message(to, frm)

        if(updates):
            spread(to,frm)

        # print!
        out = False
        print("By node: \t TTL \t \t \t GATE \t \t \t SEE \t \t \t AVG")
        for node in range(101,105+1):
            print(f"\nNode: {node}")
            for x in network_test[node]:
                print('\t',end=' ')
                q = network_test[node][x].display()
                out = out or q
    
        print("----\n")

        if(out):
            exit()

        delay = random.randint(1,4) / 2
        print(f"Delaying {delay} secs.")
        time.sleep(delay)

        # check!
        
        check = True
        for x in range(101, 105+1):
            i = None
            t = None
            ignore = True
            for item in network_test:
                i2 = network_test[item][x].get_ip_or_null()
                t2 = network_test[item][x].get_ttl()
                check = ignore or (check and i == i2 and t == t2) 
                if(ignore):
                    ignore = False
                    i = i2
                    t = t2
        if(not(check)):
            raise ValueError("Mismatch!")

        


