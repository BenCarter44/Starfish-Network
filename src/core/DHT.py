import random
from typing import Any
import numpy as np
import dill  # type: ignore
import hashlib
import src.core.star_components as star
import logging
from src.communications.main_pb2 import DHTStatus

logger = logging.getLogger(__name__)


def xor(a: bytes, b: bytes) -> bytes:
    """Calculate XOR of bytes

    Padded with 0's for longest

    Args:
        a (bytes): bytes
        b (bytes): bytes

    Returns:
        bytes: a ^ b
    """
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
    """Hash object into bytes

    Args:
        data (Any): Object to hash

    Returns:
        bytes: hash
    """
    return hashlib.sha256(dill.dumps(data)).digest()

    hsh = abs(hash(data))  # need a better one!
    hsh = hsh.to_bytes(16, "big")
    return hsh


class DHT_Response:
    def __init__(self, response_code: DHTStatus, data: Any, addrs: list[bytes]):
        """Response from DHT class

        Args:
            response_code (str): Response code
            data (Any): Value stored at hash table (or None if not found)
            addrs (list[bytes]): neighbor addresses
        """
        self.response_code = response_code
        self.data = data
        self.neighbor_addrs = addrs

    def __str__(self):
        return f"{self.response_code}: {self.data} - {self.neighbor_addrs}"


class DHT:
    def __init__(self, my_address: bytes):
        """Create a DHT

        Args:
            my_address (bytes): Address of owner
        """
        self.data: dict[Any, Any] = {}
        self.addr: set[bytes] = set()
        # for holding data that isn't supposed to be in the dictionary.
        self.cached_data: set[Any] = set()
        self.my_address: bytes = my_address

    def clear_cache(self):
        for i in self.cached_data:
            del self.data[i]

        self.cached_data.clear()

    def update_addresses(self, addr):
        if isinstance(addr, set):
            self.addr = self.addr.union(addr)
        else:
            self.addr.add(addr)

    def fetch_copy(self, owned_only=False):
        if owned_only:
            out = {}
            for i in self.data:
                if i in self.cached_data:
                    continue
                else:
                    out[i] = self.data[i]
            return out
        else:
            return self.data

    def exists(self, key: bytes):
        return key in self.data

    def remove(self, key):
        del self.data[key]
        if key in self.cached_data:
            del self.cached_data[key]

    def remove_address(self, peer):
        self.addr.remove(peer)

    def get(self, key, neighbors=3, hash_func_in=None):

        if key in self.data and key not in self.cached_data:
            return DHT_Response(DHTStatus.OWNED, self.data[key], [])

        if key in self.data and key in self.cached_data:
            return DHT_Response(DHTStatus.FOUND, self.data[key], [])

        # Not found, key probably on another node?

        if hash_func_in is None:
            primary_hash_function = hash_func
        else:
            primary_hash_function = hash_func_in

        key_hsh = primary_hash_function(key)

        # convert
        def diff_hash(obj):
            obj_hash = obj  # directly xor the address. # primary_hash_function(obj)
            return xor(obj_hash, key_hsh)

        closest = sorted(self.addr, key=diff_hash)  # sort by hash.

        # logger.debug(f"{key_hsh.hex().replace('0','')} - MAIN KEY")
        # for x in closest:
        #     tmp_hex = diff_hash(x).hex()
        #     addr_hex = x.hex()
        #     logger.debug(f"{tmp_hex.replace('0','')} - {addr_hex.replace('0','')}")

        if len(closest) < neighbors:
            close_neighbors = closest
        else:
            close_neighbors = closest[:neighbors]

        return DHT_Response(DHTStatus.NOT_FOUND, None, close_neighbors)

    def set_cache(self, key, val):
        if key in self.data and key not in self.cached_data:
            # owned! Skip!
            self.data[key] = val
            return
        self.data[key] = val
        self.cached_data.add(key)

    def fancy_print(self):
        for x in self.data:
            cache_text = "OWN  "
            if x in self.cached_data:
                cache_text = "CACHE"

            key = x.hex()
            value = self.data[x]
            if len(value.hex()) > 16:
                value = value.hex()[0:16]
                value += "..."
            else:
                value = value.hex()
            logger.debug(f"{cache_text}\t[{key}]\t = {value}")

    def set(
        self, key, val, neighbors=1, post_to_cache=True, hash_func_in=None
    ) -> DHT_Response:
        if len(key) != 8:
            logger.warning("Key in DHT set is not 8 bytes!")
        # store in myself. Then, see if there are any closer people to also send to.
        # if hash_func_in is None:
        #     primary_hash_function = hash_func
        # else:
        #     primary_hash_function = hash_func_in

        # key_hsh = primary_hash_function(key)

        # convert
        def diff_hash(obj):
            obj_hash = obj  # directly xor the address. # primary_hash_function(obj)
            return xor(obj_hash, key)

        closest = sorted(self.addr, key=diff_hash)  # sort by hash.

        logger.debug(f"{key.hex()} - MAIN KEY SET")
        logger.debug(f"Neighbor | Diff Hex")
        for x in closest:
            tmp_hex = diff_hash(x).hex()
            addr_hex = x.hex()
            logger.debug(f"{addr_hex} | {tmp_hex}")

        if len(closest) < neighbors:
            close_neighbors = closest
        else:
            close_neighbors = closest[:neighbors]

        if self.my_address not in close_neighbors:
            # My node isn't in the close neighbors, so it's supposed to be
            # owned by another closer node.
            if post_to_cache:
                self.cached_data.add(key)
                self.data[key] = val
                self.fancy_print()
            return DHT_Response(DHTStatus.FOUND, (key, val), close_neighbors)

        # if random.random() < 0.5:  # For testing the children update feature.
        #     self.cached_data.add(key)
        #     return DHT_Response("NEIGHBOR_UPDATE_CACHE", (key, val), [closest[-1]])
        self.data[key] = val
        self.fancy_print()

        return DHT_Response(DHTStatus.OWNED, (key, val), close_neighbors)


if __name__ == "__main__":

    a = star.StarTask(b"input", False)
    print(a.get_id())
    b = star.StarTask(b"input2", True)  # type: ignore
    print(b.get_id())

    addresses = [b"Address One", b"Address Two", b"Address Three"]
    dht_address_1 = DHT(addresses[0])
    dht_address_2 = DHT(addresses[1])
    dht_address_3 = DHT(addresses[2])

    dht_address_1.update_addresses(addresses)
    dht_address_2.update_addresses(addresses)
    dht_address_3.update_addresses(addresses)

    dht_address_1.set(
        b, 1, neighbors=2, hash_func_in=star.task_hash, post_to_cache=False
    )
    print(dht_address_1.get(b, neighbors=2, hash_func_in=star.task_hash))
