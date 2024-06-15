

import binascii
import string
from typing import List, Tuple

from ttl import IP_TTL, DataWithTTL
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
        self.output = [b'dummy',b'']
    
    def set_val(self, val):
        self.output[1] = val
    
    def get_val(self):
        return self.output[1]
    
    def compile(self) -> List[bytes]:
        return self.output

    def import_msg(self, data_in):
        self.output = data_in
    
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
        return b
    
    def create(self, topic):
        self.data = [0,0,0]
        self.data[0] = topic.encode('utf-8')

    def set_value(self, val : bytes):
        self.data[2] = val
    
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
        self.output[2] = int.to_bytes(r_identity, 2, 'big')
    
    def is_fetch_state(self):
        return self.output[1] == b'fetch_state'

    def is_return_state(self):
        return self.output[1] == b'return_state'

    def is_push_change(self):
        return self.output[1] == b'push_change'

    def is_push_change_receive(self):
        return self.output[1] == b'push_change_receive'

    def is_requesting_connection(self):
        return self.output[1] == b'request_connection'

    def is_requesting_connection_feedback(self):
        return self.output[1] == b'request_connection_ok'
    
    def is_requesting_disconnection(self):
        return self.output[1] == b'request_disconnection'
    
    def request_disconnect(self, r_id):
        self.output = [0,0,0]
        self.output[0] = b'General'
        self.output[1] = b'request_disconnection'
        self.output[2] = int.to_bytes(r_id, 2, 'big')
    
    def request_connection_cmd(self, r_identity):
        self.output = [0,0,0]
        self.output[0] = b'General'
        self.output[1] = b'request_connection'
        self.output[2] = int.to_bytes(r_identity, 2, 'big')

    def request_connection_feedback(self, r_identity):
        self.output = [0,0,0]
        self.output[0] = b'General'
        self.output[1] = b'request_connection_ok'
        self.output[2] = int.to_bytes(r_identity, 2, 'big')


    def return_state_receipt(self, values : List[Tuple[str, DataWithTTL]], r_identity):
        self.output = [0,0,0,0]
        self.output[0] = b'General'
        self.output[1] = b'return_state'
        self.output[2] = int.to_bytes(r_identity, 2, 'big')
        self.output[3] = int.to_bytes(len(values), 4, 'big')
        for x in values:
            self.output.append(x[0].encode('utf-8'))
            self.output.append(x[1].to_bytes())
           
    def push_change(self, key : str, value : DataWithTTL, r_identity : int):
        self.output = [0,0,0,0,0,0]
        self.output[0] = b'General'
        self.output[1] = b'push_change'
        self.output[2] = int.to_bytes(r_identity, 2, 'big')
        self.output[3] = int.to_bytes(1, 4, 'big')
        self.output[4] = key.encode('utf-8')
        self.output[5] = value.to_bytes()
    
    def get_push_key_val(self):
        dt = DataWithTTL(None,0,True)
        dt.from_bytes(self.output[5])
        return self.output[4].decode('utf-8'), dt
    
    def return_push_change(self, r_identity : int):
        self.output = [0,0,0]
        self.output[0] = b'General'
        self.output[1] = b'push_change_receive'
        self.output[2] = int.to_bytes(r_identity, 2, 'big')
       
        
    def get_state_from_return(self) -> List[Tuple[str, DataWithTTL]]:
        assert self.output[1] == b'return_state'
        length = int.from_bytes(self.output[3],'big')
        
        out = list(range(length))
        # assumes length is not lying, telling the truth
        state_data = self.output[4:]
        for x in range(length):
            dt = DataWithTTL(None, 0, True)
            dt.from_bytes(state_data[x * 2 + 1])
            out[x] = (state_data[x * 2].decode('utf-8'), dt)
        return out

    def import_msg(self, data_in):
        self.output = data_in
        if(self.output[0] != b'General' and len(self.output) < 3):
            raise ValueError("Malformed Peer KV General Message!")
    
    def get_r_identity(self):
        return int.from_bytes(self.output[2], 'big')
    
    def is_error_msg(self):
        return self.output[1] == b'Error'

    def get_error_code(self):
        return int.from_bytes(self.output[3],'big'), self.output[4].decode('utf-8')

    def error_feedback(self, code, cmd, r_identity):
        self.output = [0,0,0,0,0]
        self.output[0] = b'General'
        self.output[1] = b'Error'
        self.output[2] = int.to_bytes(r_identity, 2, 'big')
        self.output[3] = int.to_bytes(code, 2, 'big')
        self.output[4] = cmd.encode('utf-8')

    def compile_with_address(self, addr) -> List[bytes]:
        d = super(PeerKV, self).compile()
        d.insert(0,addr)
        return d



class PeerKV_Hello(PeerKV):
    def __init__(self):
        super(PeerKV_Hello, self).__init__()
        self.output = [0,0,0,0,0,0]
    
    def create(self, r_check :int, serving_endpoint_query : str):
        self.output[0] = b'Hello!'
        self.output[1] = b'key_update'
        self.output[2] = int.to_bytes(r_check, 2, 'big')
        self.output[3] = int.to_bytes(2, 4, 'big')
        self.output[4] = "blank".encode("utf-8")
        self.output[5] = serving_endpoint_query.encode("utf-8")
    
    def create_welcome(self, r_check :int):
        self.output = [0,0,0]
        self.output[0] = b'Welcome'
        self.output[1] = b'pizza!'
        self.output[2] = int.to_bytes(r_check, 2, 'big')

    def set_welcome(self):
        self.output[0] = b'Welcome'
    
    def import_msg(self, data_in):
        self.output = data_in

        if((self.output[0] != b'Hello' or self.output[0] != b'Welcome') and len(self.output) % 3 != 0):
            raise ValueError("Malformed Peer KV Hello Message!")
    
    def get_endpoint(self):
        return self.output[5].decode('utf-8')

    def get_r_identity(self):
        return int.from_bytes(self.output[2], 'big')

    def compile(self) -> List[bytes]:
        return super(PeerKV_Hello, self).compile()


if __name__ == "__main__":
    p = PeerKV_Hello()
    p.create("a","b","c")
    print(p.compile())