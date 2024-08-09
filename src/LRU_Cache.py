# The LRUCache class is based from: https://llego.dev/posts/implement-lru-cache-python/
# contains slight modifications.

# A simple LRU cache using a hashmap and a doubly linked list (Deque)

from collections import deque


class LRUCache:
    """Basic LRU Cache"""

    def __init__(self, capacity: int):
        """Define LRU Cache.

        Args:
            capacity (int): Maximum number of items to hold until items are replaced.
        """
        self.cache = dict()  # type: ignore
        self.capacity = capacity
        self.access = deque()  # type: ignore

    def __getitem__(self, key):
        return self.get(key)

    def get(self, key):
        """Get item at key in cache

        Args:
            key (any): key

        Returns:
            any: item
        """
        if key not in self.cache:
            return -1
        else:
            self.access.remove(key)
            self.access.append(key)
            return self.cache[key]

    def __contains__(self, key):
        return self.contains(key)

    def contains(self, key):
        return key in self.cache

    def __setitem__(self, key, value):
        return self.put(key, value)

    def put(self, key, value):
        """Put item at key

        Args:
            key (any): Key
            value (any): Value
        """
        if key in self.cache:
            self.access.remove(key)
        elif len(self.cache) == self.capacity:
            oldest = self.access.popleft()
            del self.cache[oldest]
        self.cache[key] = value
        self.access.append(key)

    def print(self):
        """Pretty print cache"""
        for key in self.access:
            print(f"{key}: {self.cache[key]}")

    def __repr__(self):
        return self.cache.__repr__()

    def __str__(self):
        return self.cache.__str__()
