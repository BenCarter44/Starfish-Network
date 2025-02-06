import os
import numpy as np


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
    random_value = np.random.normal(mean_int, std_dev)

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
            filtered_str.append(27)
        if i >= 65 and i < 91:
            filtered_str.append(i - 65 + 1)  # 0 is BLANK

    while len(filtered_str) < 6:
        filtered_str.append(0)

    total = 0
    for i, num in enumerate(filtered_str):
        total += 28**i * num
    return total.to_bytes(4, "big", signed=False)


def decompress_bytes_to_str(b: bytes) -> str:
    total = int.from_bytes(b, "big", signed=False)
    filtered_str = []
    out = ""
    for c in range(6):
        filtered_str.append(total % 28)
        total = total // 28

    for token in filtered_str:
        if token == 0:
            continue
        if token == 27:
            out += "/"
            continue
        character = token - 1 + 65
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

if __name__ == "__main__":
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
