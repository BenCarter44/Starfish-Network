

import binascii
import string
from typing import List

from ttl import DataWithTTL
import dill

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

class BasicMultipartMessage():
    def __init__(self):
        self.output = []
    
    def compile(self) -> List[bytes]:
        return self.output

    def import_msg(self, data_in):
        self.data = data_in
    
    def compile_with_address(self, addr) -> List[bytes]:
        d = self.compile()
        d.insert(0,addr)
        return d

class PeerKV_Subscribe(BasicMultipartMessage):
    def __init__(self):
        super(PeerKV_Subscribe, self).__init__()
    
    def import_msg(self, data_in):
        self.data = data_in
    
    def get_topic(self) -> str:
        return self.data[0].decode('utf-8')

    def get_key(self):
        return self.data[1].decode('utf-8')

    def get_value(self):
        b = self.data[2]
        c = self.data[3]
        val = dill.loads(b) # can be Null
        ttl = float(c.decode('utf-8'))
        return DataWithTTL(val, ttl)
    
    def create(self, topic):
        self.data = [0,0,0,0]
        self.data[0] = topic.encode('utf-8')

    def set_value(self, val : DataWithTTL):
        self.data[2] = dill.dumps(val.get_value_or_null())
        self.data[3] = str(val.get_timeout()).encode("utf-8")
    
    def set_key(self, key):
        self.data[1] = key.encode('utf-8')

    def compile(self) -> List[bytes]:
        return self.data


     
class PeerKV(BasicMultipartMessage):
    def __init__(self):
        super(PeerKV, self).__init__()
        self.output = [0]
        self.output[0] = b'General'
    
    def compile(self) -> List[bytes]:
        return super(PeerKV, self).compile()
    
    def fetch_state_command(self, r_identity):
        self.output = [0,0,0]
        self.output[0] = b'General'
        self.output[1] = b'fetch_state'
        self.output[2] = int.to_bytes(r_identity, 2)
    
    def is_fetch_state(self):
        return self.output[1] == b'fetch_state'

    def is_return_state(self):
        return self.output[1] == b'return_state'

    def is_push_change(self):
        return self.output[1] == b'push_change'

    def is_push_change_receive(self):
        return self.output[1] == b'push_change_receive'

    def return_state_receipt(self, values : List[DataWithTTL], r_identity):
        self.output = [0,0,0,0]
        self.output[0] = b'General'
        self.output[1] = b'return_state'
        self.output[2] = int.to_bytes(r_identity, 2)
        self.output[3] = int.to_bytes(len(values), 4)
        for x in values:
            val = dill.dumps(x.get_value_or_null())
            self.output.append(val)
            self.output.append(str(x.get_timeout()).encode("utf-8"))
    
    def push_change(self, key : str, value : DataWithTTL, r_identity : int):
        self.output = [0,0,0,0,0,0,0]
        self.output[0] = b'General'
        self.output[1] = b'push_change'
        self.output[2] = int.to_bytes(r_identity, 2)
        self.output[3] = int.to_bytes(1, 4)

        val = dill.dumps(value.get_value_or_null())
        self.output[4] = key.encode('utf-8')
        self.output[5] = val
        self.output[6] = (str(value.get_timeout()).encode("utf-8"))
    
    def get_push_key_val(self):
        return self.output[4].decode('utf-8'), DataWithTTL(dill.loads(self.output[5]),float(self.output[6].decode('utf-8')))
    
    def return_push_change(self, r_identity : int):
        self.output = [0,0,0]
        self.output[0] = b'General'
        self.output[1] = b'push_change_receive'
        self.output[2] = int.to_bytes(r_identity, 2)
       
        
    def get_state_from_return(self) -> List[DataWithTTL]:
        assert self.output[1] == b'return_state'
        length = int.from_bytes(self.output[3])
        
        out = list(range(length))
        # assumes length is not lying, telling the truth
        state_data = self.output[4:]
        for x in range(length):
            out[x] = DataWithTTL(dill.loads(state_data[x * 2]),float(state_data[x * 2 +1].decode('utf-8')))
        
        return out

    def import_msg(self, data_in):
        self.output = data_in
        if(self.output[0] != b'General' and len(self.output) < 3):
            raise ValueError("Malformed Peer KV General Message!")
    
    def get_r_identity(self):
        return int.from_bytes(self.output[2])
    
    def compile_with_address(self, addr) -> List[bytes]:
        d = super(PeerKV, self).compile()
        d.insert(0,addr)
        return d



class PeerKV_Hello(PeerKV):
    def __init__(self):
        super(PeerKV_Hello, self).__init__()
        self.output = [0,0,0,0,0,0,0,0]
    
    def create(self, r_check :int, serving_endpoint_pub : str, serving_endpoint_query : str, ttl : float):
        self.output[0] = b'Hello!'
        self.output[1] = b'key_update'
        self.output[2] = int.to_bytes(r_check, 2)
        self.output[3] = int.to_bytes(2, 4)
        self.output[4] = serving_endpoint_pub.encode("utf-8")
        self.output[5] = str(ttl).encode("utf-8")
        self.output[6] = serving_endpoint_query.encode("utf-8")
        self.output[7] = str(ttl).encode("utf-8")
    
    def set_welcome(self):
        self.output[0] = b'Welcome'
    
    def import_msg(self, data_in):
        self.output = data_in

        if((self.output[0] != b'Hello' or self.output[0] != b'Welcome') and len(self.output) != 8):
            raise ValueError("Malformed Peer KV Hello Message!")
    
    def get_endpoints(self):
        return DataWithTTL(self.output[4].decode('utf-8'),float(self.output[5].decode("utf-8")),True), DataWithTTL(self.output[6].decode('utf-8'),float(self.output[7].decode("utf-8")),True)

    def get_r_identity(self):
        return int.from_bytes(self.output[2])

    def compile(self) -> List[bytes]:
        return super(PeerKV_Hello, self).compile()


if __name__ == "__main__":
    p = PeerKV_Hello()
    p.create("a","b","c")
    print(p.compile())