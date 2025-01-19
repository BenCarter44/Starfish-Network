"""A file implementing a Distributed Hash Table Class

By Benjamin Carter - 2025

It is a simple wrapper to the python dict, but also searches a list of 
peer addresses to send the key to. It doesn't do the actual sending, but rather
informs the user what peer would be more appropriate for the key to be stored under.

"""

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
    # append 0s to MSB until same size.
    if a_len > b_len:
        b_buf = np.pad(b_buf, (a_len - b_len, 0), "constant", constant_values=(0,))
    elif b_len > a_len:
        a_buf = np.pad(a_buf, (b_len - a_len, 0), "constant", constant_values=(0,))

    return (a_buf ^ b_buf).tobytes()


def hash_func(data: Any) -> bytes:
    """Hash object into bytes

    A basic function to hash a key into bytes. Relies on dill.

    Args:
        data (Any): Object to hash

    Returns:
        bytes: hash
    """
    return hashlib.sha256(dill.dumps(data)).digest()


class DHT_Response:
    def __init__(self, response_code: DHTStatus, data: Any, addrs: list[bytes]):
        """Response from DHT class

        A struct.

        Args:
            response_code (DHTStatus): Response code
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
        """A DHT object for one node.

        Args:
            my_address (bytes): Address of owner
        """
        self.data: dict[Any, Any] = {}
        self.addr: set[bytes] = set()

        # for holding keys in the dictionary that are only there for caching.
        self.cached_data: set[Any] = set()
        self.my_address: bytes = my_address

    def clear_cache(self):
        for i in self.cached_data:
            del self.data[i]

        self.cached_data.clear()

    def update_addresses(self, addr: set[bytes] | bytes):
        if isinstance(addr, set):
            self.addr = self.addr.union(addr)
        else:
            self.addr.add(addr)

    def fetch_dict(self, skip_cache=False):
        """Fetch a python dict representation.

        Args:
            skip_cache (bool, optional): True to skip cached values. Defaults to False.

        Returns:
            dict: Dictionary of the local copy of the DHT.
        """
        if skip_cache:
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

    def remove(self, key: bytes):
        """Remove key from dictionary. Is idempotent.

        Args:
            key (bytes): Key to remove.
        """
        if key in self.data:
            del self.data[key]
        if key in self.cached_data:
            self.cached_data.remove(key)

    def remove_address(self, peer: bytes):
        """Remove address from address list.

        Args:
            peer (bytes): Bytes of peer address.
        """
        if peer in self.addr:
            self.addr.remove(peer)

    def get(self, key: bytes, neighbors=3, ignore: set[bytes] = set()):
        """Fetch an item from the DHT.

        Args:
            key (bytes): Key
            neighbors (int, optional): Number of neighbors to return if not found on local. Defaults to 3.

        Returns:
            _type_: _description_
        """
        if key in self.data and key not in self.cached_data:
            return DHT_Response(DHTStatus.OWNED, self.data[key], [])

        if key in self.data and key in self.cached_data:
            return DHT_Response(DHTStatus.FOUND, self.data[key], [])

        # convert
        def diff_hash(obj):
            # directly xor the address. They are already bytes that are unique.
            return xor(obj, key)

        query_addresses = self.addr.difference(ignore)

        closest = sorted(query_addresses, key=diff_hash)  # sort by hash.

        if len(closest) < neighbors:
            close_neighbors = closest
        else:
            close_neighbors = closest[:neighbors]

        return DHT_Response(DHTStatus.NOT_FOUND, None, close_neighbors)

    def set_cache(self, key: bytes, val: Any):
        """Set item but mark it as cached.

        This ignores all the distributed algorithms.

        Args:
            key (bytes): key of object to store
            val (Any): value of object to store

        Returns:
            bool: True if cached.
        """
        if key in self.data and key not in self.cached_data:
            # owned! overwrite!
            self.data[key] = val
            return False

        self.data[key] = val
        self.cached_data.add(key)

        return True

    def fancy_print(self):
        """Dump values in DHT"""
        for x in self.data:
            cache_text = "OWN  "
            if x in self.cached_data:
                cache_text = "CACHE"

            key = x.hex()
            value = self.data[x]
            assert value != b""
            if len(value.hex()) > 16:
                value = value.hex()[0:16]
                value += "..."
            else:
                value = value.hex()
            logger.info(f"{cache_text}\t[{key}]\t = {value}")

    def set(
        self,
        key: bytes,
        val: Any,
        neighbors=1,
        post_to_cache=True,
        ignore: set[bytes] = set(),
    ) -> DHT_Response:
        """Set object in DHT. Forward to neighbors who are closer.

        Args:
            key (bytes): key
            val (Any): Value to store
            neighbors (int, optional): Neighbors to forward who are closer. Defaults to 1.
            post_to_cache (bool, optional): Add to local cache if there are peers closer. Defaults to True.

        Returns:
            DHT_Response: _description_
        """
        if len(key) != 8:
            logger.warning("Key in DHT set is not 8 bytes!")

        # store in myself. Then, see if there are any closer people to also send to.

        # convert
        def diff_hash(obj):
            obj_hash = obj  # directly xor the address. # primary_hash_function(obj)
            return xor(obj_hash, key)

        query_addresses = self.addr.difference(ignore)

        closest = sorted(query_addresses, key=diff_hash)  # sort by hash.

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

            return DHT_Response(DHTStatus.FOUND, (key, val), close_neighbors)

        self.data[key] = val
        return DHT_Response(DHTStatus.OWNED, (key, val), close_neighbors)


# if __name__ == "__main__":

#     a = star.StarTask(b"input", False)
#     print(a.get_id())
#     b = star.StarTask(b"input2", True)  # type: ignore
#     print(b.get_id())

#     addresses = [b"Address One", b"Address Two", b"Address Three"]
#     dht_address_1 = DHT(addresses[0])
#     dht_address_2 = DHT(addresses[1])
#     dht_address_3 = DHT(addresses[2])

#     dht_address_1.update_addresses(addresses)
#     dht_address_2.update_addresses(addresses)
#     dht_address_3.update_addresses(addresses)

#     dht_address_1.set(
#         b, 1, neighbors=2, hash_func_in=star.task_hash, post_to_cache=False
#     )
#     print(dht_address_1.get(b, neighbors=2, hash_func_in=star.task_hash))
