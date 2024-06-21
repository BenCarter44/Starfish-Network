import binascii
import os
import string
import zmq


def dump(msg: list[bytes]) -> None:
    """Display raw output of zmq messages

    Args:
        msg (list[bytes]): zmq multipart message
    """
    for part in msg:
        print("[%03d]" % len(part), end=" ")
        try:
            s_raw = part.decode("ascii")
            for x in s_raw:
                if x not in string.printable:
                    raise ValueError
            print(s_raw)
        except (UnicodeDecodeError, ValueError) as e:
            print(r"0x %s" % (binascii.hexlify(part, " ").decode("ascii")))


def zpipe(ctx: zmq.Context) -> tuple[zmq.Socket, zmq.Socket]:
    """build inproc pipe for talking to threads

    mimic pipe used in czmq zthread_fork.

    Args:
        ctx (zmq.Context): Context
    Returns:
        tuple[zmq.Socket, zmq.Socket]: Returns a pair of PAIRs connected via inproc
    """
    a = ctx.socket(zmq.PAIR)
    b = ctx.socket(zmq.PAIR)
    a.linger = b.linger = 0
    a.hwm = b.hwm = 1
    iface = "inproc://%s" % binascii.hexlify(os.urandom(8)).decode("utf-8")
    a.bind(iface)
    b.connect(iface)
    return a, b
