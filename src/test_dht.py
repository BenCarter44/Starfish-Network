from src.core.DHT import DHT


class Number:
    def __init__(self, num, other, callable=None):
        self.num = num
        self.other = other
        self.callable = callable

    def __eq__(self, value):
        if isinstance(value, Number):
            return value.num == self.num
        else:
            return False

    def __repr__(self):
        return f"<{self.num}:{self.other}>"

    def __hash__(self):
        return hash(self.num)


a: dict[Number, int] = {}
a_dht = DHT(b"Hello!")
a_dht.update_addresses([b"Hello!"])


def sample():
    print("Sample!")


a[Number(1, 0, sample)] = 10
a_dht.set(Number(1, 1), 10)
a[Number(2, 0)] = 20
a_dht.set(Number(2, 2), 20)
a[Number(3, 0)] = 30
a_dht.set(Number(3, 3), 30)

print(a)
print(a_dht.data)

########## GET
print(a[Number(1, 0)])
resp = a_dht.get(Number(1, 0))
print(resp.data)

print(Number(1, 0) in a)
for x in a:
    print(x)
    print(x.callable)

print(a[Number(2, 0)])
resp = a_dht.get(Number(2, 0))
print(resp.data)
print(a[Number(3, 0)])
resp = a_dht.get(Number(3, 0))
print(resp.data)
