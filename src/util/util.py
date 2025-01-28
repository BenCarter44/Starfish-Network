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
