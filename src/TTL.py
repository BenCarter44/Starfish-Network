import time
from typing import Any, Optional
import dill


class DataTTL:
    """Data with a time-to-live feature"""

    def __init__(self, data: Any, timeout: float, suppress_error: bool = False):
        """Initiate a simple data object with Time-To-Live. Supposed to be immutable.

        Args:
            data (Any): Data to store
            timeout (float): timeout in UNIX timestamp.
            suppress_error (bool): Set to true to ignore ValueError on creation

        Raises:
            ValueError: If timeout is in the past, raise ValueError.
        """
        self.__data = data
        self.__timeout = timeout
        self.__time_created = time.time()
        if not (suppress_error) and self.__timeout < self.__time_created:
            raise ValueError("Timeout in the past!")

    def get_value(self) -> Any:
        """Get value stored

        Raises:
            ValueError: If past TTL, throw exception.

        Returns:
            Any: Data stored.
        """
        if self.__timeout > time.time():
            return self.__data
        else:
            raise ValueError("Value Expired!")

    def get_timeout(self) -> float:
        """Return the timeout

        Returns:
            float: Timeout in UNIX seconds.
        """
        return self.__timeout

    def is_valid(self) -> bool:
        """Return true if still alive

        Returns:
            bool: True if alive
        """
        return self.__timeout > time.time()

    def get_value_or_null(self) -> Optional[Any]:
        """Get value stored, or return None if past TTL.

        Returns:
            Optional[Any]: Data stored or None if past TTL.
        """
        if self.__timeout > time.time():
            return self.__data
        else:
            return None

    def to_bytes(self) -> bytes:
        """Serialize data object to bytes

        Returns:
            bytes: Byte serialization of the data
        """
        return dill.dumps((self.__data, self.__timeout))

    def get_raw_val(self):
        """Get raw value even if it expired

        Returns:
            any: _description_
        """
        return self.__data

    def from_bytes(self, byt: bytes):
        """Extract from serialized bytes

        Args:
            byt (bytes): Serialized bytes
        """
        ext: tuple[Any, float] = dill.loads(byt)
        self.__data = ext[0]
        self.__timeout = ext[1]
        self.__time_created = time.time()
