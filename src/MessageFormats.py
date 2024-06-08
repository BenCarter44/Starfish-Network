

import binascii
from typing import List

from ttl import DataWithTTL
import dill

def dump(msg):
    for part in msg:
        print("[%03d]" % len(part), end=' ')
        is_text = True
        try:
            print(part.decode('utf-8'))
        except UnicodeDecodeError:
            print(r"0x%s" % (binascii.hexlify(part).decode('utf-8')))

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

class PeerKV(BasicMultipartMessage):
    def __init__(self):
        super(PeerKV, self).__init__()
        self.output = [0]
        self.output[0] = b'General'
    
    def compile(self) -> List[bytes]:
        return super(PeerKV, self).compile()
    
    def fetch_state_command(self):
        self.output = [0,0]
        self.output[0] = b'General'
        self.output[1] = b'fetch_state'
    
    def is_fetch_state(self):
        return self.output[1] == b'fetch_state'

    def is_return_state(self):
        return self.output[1] == b'return_state'

    def return_state_receipt(self, values : List[DataWithTTL]):
        self.output = [0,0,0]
        self.output[0] = b'General'
        self.output[1] = b'return_state'
        self.output[2] = bytes([len(values)])
        for x in values:
            val = dill.dumps(x.get_value_or_null())
            self.output.append(val)
            self.output.append(str(x.get_timeout()).encode("utf-8"))
        
    def get_state_from_return(self) -> List[DataWithTTL]:
        assert self.output[1] == b'return_state'
        length = int.from_bytes(self.output[2])
        
        out = list(range(length))
        # assumes length is not lying, telling the truth
        state_data = self.output[3:]
        for x in range(length):
            out[x] = DataWithTTL(dill.loads(state_data[x * 2]),float(state_data[x * 2 +1].decode('utf-8')))
        
        return out

    def import_msg(self, data_in):
        self.output = data_in
        if(self.output[0] != b'General' and len(self.output) < 2):
            raise ValueError("Malformed Peer KV General Message!")
    
    
    def compile_with_address(self, addr) -> List[bytes]:
        d = super(PeerKV, self).compile()
        d.insert(0,addr)
        return d


class PeerKV_Hello_Receipt(PeerKV):
    def __init__(self):
        super(PeerKV_Hello_Receipt, self).__init__()
        self.output = [0]
    
    def create(self):
        self.output[0] = b'Welcome'
    
    def import_msg(self, data_in):
        self.output = data_in

        if(self.output[0] != b'Welcome' and len(self.output) != 1):
            raise ValueError("Malformed Peer KV Welcome Message!")
    
    def compile(self) -> List[bytes]:
        return super(PeerKV_Hello_Receipt, self).compile()

    def compile_with_address(self, addr) -> List[bytes]:
        d = super(PeerKV_Hello_Receipt, self).compile()
        d.insert(0,addr)
        return d

class PeerKV_Hello(PeerKV):
    def __init__(self):
        super(PeerKV_Hello, self).__init__()
        self.output = [0,0,0,0,0,0,0]
    
    def create(self, serving_endpoint_pub : str, serving_endpoint_query : str, ttl : float):
        self.output[0] = b'Hello!'
        self.output[1] = b'key_update'
        self.output[2] = bytes([2])
        self.output[3] = serving_endpoint_pub.encode("utf-8")
        self.output[4] = str(ttl).encode("utf-8")
        self.output[5] = serving_endpoint_query.encode("utf-8")
        self.output[6] = str(ttl).encode("utf-8")
    
    def import_msg(self, data_in):
        self.output = data_in

        if(self.output[0] != b'Hello' and len(self.output) != 7):
            raise ValueError("Malformed Peer KV Hello Message!")
    
    def get_endpoints(self):
        return DataWithTTL(self.output[3],float(self.output[4].decode("utf-8")),True), DataWithTTL(self.output[5],float(self.output[6].decode("utf-8")),True)

    def compile(self) -> List[bytes]:
        return super(PeerKV_Hello, self).compile()


if __name__ == "__main__":
    p = PeerKV_Hello()
    p.create("a","b","c")
    print(p.compile())