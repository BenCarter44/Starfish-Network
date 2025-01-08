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


if __name__ == "__main__":
    # Example usage
    mean_bytes = bytes.fromhex("5f294862")
    std_dev_bytes = bytes.fromhex("2727")
    result = gaussian_bytes(mean_bytes, std_dev_bytes, 32)
    print(result.hex())
