import os
import random
import math


def random_normal(mean=0, stddev=1):
    """Generate a random number following a normal distribution using Box-Muller transform."""
    u1, u2 = (
        random.random(),
        random.random(),
    )  # Two independent uniform random variables
    z0 = math.sqrt(-2 * math.log(u1)) * math.cos(
        2 * math.pi * u2
    )  # Standard normal variable
    return mean + z0 * stddev  # Scale and shift to desired mean and std deviation


def gaussian_bytes(mean: bytes, std_dev: bytes | int, length: int) -> bytes:
    """
    Generate a random bytes object sampled from a Gaussian distribution.

    Parameters:
        mean (bytes): Mean of the Gaussian distribution as a bytes object.
        std_dev (bytes): Standard deviation of the Gaussian distribution as a bytes object.
        length (int): Number of bytes to generate.

    Returns:
        bytes: Random bytes sampled from the Gaussian distribution.
    """
    # Convert bytes to integers
    mean_int = int.from_bytes(mean, byteorder="big", signed=False)
    if isinstance(std_dev, bytes):
        std_dev = int.from_bytes(std_dev, byteorder="big", signed=False)

    # Generate random Gaussian values
    random_value = random_normal(mean_int, std_dev)

    # Clip the value to be within valid byte range   # 1 << 5 same as 2^5
    clipped_value = max(0, min(random_value, (1 << (8 * length)) - 1))

    # Convert the value back to bytes
    return int(clipped_value).to_bytes(length, byteorder="big", signed=False)


def compress_str_to_bytes(s: str) -> bytes:
    if len(s) > 6:
        raise ValueError("Too long! 6 char max!")
    filtered_str = []
    for character in s.upper():
        i = ord(character)
        if i == 47:
            filtered_str.append(1)
        if i >= 65 and i < 91:
            filtered_str.append(i - 65 + 2)  # 0 is BLANK

    while len(filtered_str) < 6:
        filtered_str.append(0)

    total = 0
    for i, num in enumerate(filtered_str):
        total += 28**i * num
    return total.to_bytes(4, "little", signed=False)


def decompress_bytes_to_str(b: bytes) -> str:
    total = int.from_bytes(b, "little", signed=False)
    filtered_str = []
    out = ""
    for c in range(6):
        filtered_str.append(total % 28)
        total = total // 28

    for token in filtered_str:
        if token == 0:
            continue
        if token == 1:
            out += "/"
            continue
        character = token - 2 + 65
        out += chr(character)
    return out


def and_bytes(a: bytes, b: bytes):
    assert len(a) == len(b)
    c = (int.from_bytes(a, "big") & int.from_bytes(b, "big")).to_bytes(
        max(len(a), len(b)), "big"
    )
    return c


def or_bytes(a: bytes, b: bytes):
    assert len(a) == len(b)
    c = (int.from_bytes(a, "big") | int.from_bytes(b, "big")).to_bytes(
        max(len(a), len(b)), "big"
    )
    return c


def not_bytes(input_bytes: bytes) -> bytes:
    """
    Perform a bitwise NOT operation on a bytes object.

    Args:
        input_bytes (bytes): The input bytes object.

    Returns:
        bytes: A new bytes object with the bitwise NOT applied to each byte.
    """
    return bytes(~b & 0xFF for b in input_bytes)


def xor_bytes(a: bytes, b: bytes):
    assert len(a) == len(b)
    c = (int.from_bytes(a, "big") ^ int.from_bytes(b, "big")).to_bytes(
        max(len(a), len(b)), "big"
    )
    assert c == xor(a, b)
    return c


def xor(a: bytes, b: bytes) -> bytes:
    """Calculate XOR of bytes, padded with 0's for the longest.

    Args:
        a (bytes): First byte sequence.
        b (bytes): Second byte sequence.

    Returns:
        bytes: Result of a ^ b with zero-padding to match the longer input.
    """
    a_len, b_len = len(a), len(b)
    max_len = max(a_len, b_len)

    # Pad the shorter byte sequence with 0s
    a_padded = a.rjust(max_len, b"\x00")
    b_padded = b.rjust(max_len, b"\x00")

    # Perform XOR operation
    return bytes(x ^ y for x, y in zip(a_padded, b_padded))


def pad_bytes(b: bytes, l: int) -> bytes:
    """Pad bytes on left (most significant bit first, big endian)

    Args:
        b (bytes): bytes to pad
        l (int): length

    Returns:
        bytes: The padded bytes
    """
    data = bytearray(b)
    padding_byte = b"\x00"
    data = data.rjust(l, padding_byte)  # pad on MSB
    return bytes(data)


import base64


def encode_to_base32(data: bytes) -> str:
    """
    Encodes bytes to a Base32 string.

    Args:
        data (bytes): The bytes to encode.

    Returns:
        str: Base32 encoded string.
    """
    s = base64.b32encode(data).decode("utf-8")
    return s.replace("=", "").lower()


def decode_from_base32(encoded_data: str) -> bytes:
    """
    Decodes bytes to a Base32 string.

    Args:
        data (str): The string to decode.

    Returns:
        bytes: bytes
    """
    while len(encoded_data) % 8 > 0:
        encoded_data += "="
    return base64.b32decode(encoded_data.upper())


def join_paths(*paths: str) -> str:
    normalized_paths = [
        path.replace("\\", os.sep).replace("/", os.sep) for path in paths
    ]
    return os.path.join(*normalized_paths)


if __name__ == "__main2__":
    # Example usage
    mean_bytes = bytes.fromhex("5f294862")
    std_dev_bytes = bytes.fromhex("2727")
    result = gaussian_bytes(mean_bytes, std_dev_bytes, 32)
    print(result.hex())

if __name__ == "__main3__":
    t = "HELLO"
    b = compress_str_to_bytes(t)
    s = decompress_bytes_to_str(b)
    print(t)
    print(b)
    print(s)
    assert t.upper() == s

    t = "Hello/"
    b = compress_str_to_bytes(t)
    s = decompress_bytes_to_str(b)
    print(t)
    print(b)
    print(s)
    assert t.upper() == s

    t = "abc"
    b = compress_str_to_bytes(t)
    s = decompress_bytes_to_str(b)
    print(t)
    print(b)
    print(s)
    assert t.upper() == s

    t = "/up/"
    b = compress_str_to_bytes(t)
    s = decompress_bytes_to_str(b)
    print(t)
    print(b)
    print(s)
    assert t.upper() == s
