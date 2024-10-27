import random
from typing import Any
import numpy as np
import dill
import hashlib


def xor(a: bytes, b: bytes) -> bytes:
    a_buf = np.frombuffer(a, dtype=np.uint8)
    b_buf = np.frombuffer(b, dtype=np.uint8)
    a_len = a_buf.shape[0]
    b_len = b_buf.shape[0]
    if a_len > b_len:
        b_buf = np.pad(b_buf, (a_len - b_len, 0), "constant", constant_values=(0,))
    elif b_len > a_len:
        a_buf = np.pad(a_buf, (b_len - a_len, 0), "constant", constant_values=(0,))
    # append 0s to MSB until same size.

    return (a_buf ^ b_buf).tobytes()


def hash_func(data: Any) -> bytes:

    return hashlib.sha256(dill.dumps(data)).digest()

    hsh = abs(hash(data))  # need a better one!
    hsh = hsh.to_bytes(16, "big")
    return hsh


class DHT_Response:
    def __init__(self, response_code: str, data: Any, addrs: list[bytes]):
        self.response_code = response_code
        self.data = data
        self.neighbor_addrs = addrs

    def __str__(self):
        return f"{self.response_code}: {self.data} - {self.addrs}"


class DHT:
    def __init__(self, my_address: bytes):
        self.data = {}
        self.addr = []
        # for holding data that isn't supposed to be in the dictionary.
        self.cached_data = set()
        self.my_address: bytes = my_address

    def update_addresses(self, addr):
        self.addr = addr

    def get(self, key, neighbors=3):
        if key in self.data:
            return DHT_Response(self, "SELF_FOUND", self.data[key], [])
        # Not found, key probably on another node?

        key_hsh = hash_func(key)

        def diff_hash(obj):
            obj_hash = hash_func(obj)
            return xor(obj_hash, key_hsh)

        closest = sorted(self.addr, key=diff_hash)  # sort by hash.

        print(f"{'00'*32} - {key_hsh.hex()} - MAIN KEY {key}")
        for x in closest:
            obj_hsh = hash_func(x)
            print(f"{diff_hash(x).hex()} - {obj_hsh.hex()} - {x}")

        if len(closest) < neighbors:
            close_neighbors = closest
        else:
            close_neighbors = closest[:neighbors]

        return DHT_Response("NOT_FOUND", None, close_neighbors)

    def set(self, key, val, neighbors=3) -> DHT_Response:
        # store in myself. Then, see if there are any closer people to also send to.
        self.data[key] = val

        key_hsh = hash_func(key)
        print(f"Key HSH: {key_hsh.hex()}")

        # convert
        def diff_hash(obj):
            obj_hash = hash_func(obj)
            return xor(obj_hash, key_hsh)

        closest = sorted(self.addr, key=diff_hash)  # sort by hash.

        print(f"{'00'*32} - {key_hsh.hex()} - MAIN KEY {key}")
        for x in closest:
            obj_hsh = hash_func(x)
            print(f"{diff_hash(x).hex()} - {obj_hsh.hex()} - {x}")

        if len(closest) < neighbors:
            close_neighbors = closest
        else:
            close_neighbors = closest[:neighbors]

        if self.my_address not in close_neighbors:
            # My node isn't in the close neighbors, so it's supposed to be
            # owned by another closer node.
            self.cached_data.add(key)
            return DHT_Response("NEIGHBOR_UPDATE_CACHE", (key, val), close_neighbors)

        # if random.random() < 0.5:  # For testing the children update feature.
        #     self.cached_data.add(key)
        #     return DHT_Response("NEIGHBOR_UPDATE_CACHE", (key, val), [closest[-1]])

        return DHT_Response("NEIGHBOR_UPDATE_AND_OWN", (key, val), close_neighbors)


if __name__ == "__main__":

    addresses = [b"Address One", b"Address Two", b"Address Three"]
    dht_address_1 = DHT(addresses[0])
    dht_address_2 = DHT(addresses[1])
    dht_address_3 = DHT(addresses[2])

    dht_address_1.update_addresses(addresses)
    dht_address_2.update_addresses(addresses)
    dht_address_3.update_addresses(addresses)

    print(dht_address_1.set("Hello! One", 1, neighbors=2))
    print(dht_address_2.set("Hello! Two", 2, neighbors=2))
    print(dht_address_3.set("Hello! Three", 3, neighbors=2))