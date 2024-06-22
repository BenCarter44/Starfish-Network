import datetime
import threading
import time
from typing import Any, Callable, Dict, Optional, cast
from typing_extensions import Self
import dill  # type: ignore

dict_keys = type({}.keys())  # type: ignore


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


class DataTTL_Library:
    """Manager that automatically dispatches updates to DataTTL pairs"""

    def __init__(self, send_handler: Callable[[str, DataTTL], None]):
        """Start up DataTTL manager

        Args:
            send_handler (Callable): Function to execute on pushed changes
        """
        self.data: dict[str, DataTTL] = {}
        self.UPDATE_OFFSET = 0.75  # 75 percent window.
        self.cache: Dict[str, Optional[DataTTL]] = {}
        self.evt = threading.Event()
        self.is_stop = False
        self.th = threading.Thread(None, self.__wait_thread)
        self.th.start()
        self.send_msg = send_handler
        self.edit: dict[str, float] = {}

    def add_data_TTL(self, key: str, data: DataTTL):
        """Add DataTTL to the library

        Args:
            key (str): Key
            data (DataWithTTL): DataTTL Pair
        """
        self.data[key] = data
        self.cache[key] = None
        self.edit[key] = time.time()

    def get_keys(self, ignore=False) -> Any:  # type: ignore
        """Get all keys in the library

        Args:
            ignore (bool, optional): Ignore expired. Defaults to False.

        Returns:
            dict_keys[str, DataWithTTL]: list of keys available
        """
        if ignore:
            return self.data.keys()

        result = {}  # TODO: Change to generator.
        for x in self.data.keys():
            if self.data[x].get_value_or_null() is not None:
                result[x] = self.data[x].get_value_or_null()
        return result.keys()

    def add_merge_data_TTL(self, key: str, data: DataTTL):
        """Merge in/add a key and DataTTL

        Args:
            key (str): Key
            data (DataWithTTL): Data TTL
        """
        if key in self.data:
            self.merge(key, data)
        else:
            self.add_data_TTL(key, data)

    def del_key(self, key: str):
        """Delete key from library. Assumes it already exists

        Args:
            key (str): The key to delete from
        """
        del self.data[key]
        del self.cache[key]
        del self.edit[key]

    def prune(self):
        """Delete all keys that have expired"""
        delete = []
        for x in self.data:
            if self.data[x].get_value_or_null() is None:
                delete.append(x)

        for d in delete:
            self.del_key(d)

    def stop(self):
        """Stop the updating thread. There is no going back!"""
        self.is_stop = True
        self.evt.set()
        self.th.join()

    def get_window(self, large: float, small: float):
        """Get the limit time before pushing updates

        Args:
            large (float): timestamp of TTL
            small (float): timestamp of time added

        Returns:
            float: timestamp of when to start sending updates
        """
        return (large - small) * self.UPDATE_OFFSET + small

    def merge(self, key: str, inc: DataTTL) -> bool:
        """Merge in a DataTTL record. Send updates to callback as necessary

        Args:
            key (str): key
            inc (DataWithTTL): DataTTL Pair

        Returns:
            bool: True if DataTTL Pair is updated
        """
        if key not in self.data:
            self.add_data_TTL(key, inc)
            self.send_msg(key, self.data[key])
            return True

        if inc.get_timeout() < self.data[key].get_timeout() + 1:
            # force at least one sec update
            return False  # drop

        # if inc.get_timeout() > self.data[key].get_timeout()

        if (
            self.get_window(self.data[key].get_timeout(), self.edit[key]) > time.time()
        ):  # still got time
            if self.cache[key] is not None:
                r = cast(DataTTL, self.cache[key]).get_timeout()
                if inc.get_timeout() > r:
                    self.cache[key] = inc
                    self.evt.set()
            else:
                self.cache[key] = inc
                self.evt.set()

            return False

        # else

        if (
            self.cache[key] is not None
            and inc.get_timeout() > cast(DataTTL, self.cache[key]).get_timeout()
        ):
            # clear cache
            self.cache[key] = None
            self.evt.set()
            self.data[key] = inc
            self.edit[key] = time.time()
            self.send_msg(key, self.data[key])
            return True

        if self.cache[key] is not None:
            # cache time is greater
            self.data[key] = cast(DataTTL, self.cache[key])
            self.cache[key] = None
            self.edit[key] = time.time()
            self.evt.set()
            self.send_msg(key, self.data[key])
            return True

        # cache is none
        assert self.cache[key] is None
        self.data[key] = inc
        self.edit[key] = time.time()
        self.send_msg(key, self.data[key])
        return True

    def __wait_thread(self):
        """Timer thread"""
        while True:
            self.evt.wait(0.5)
            if self.is_stop:
                break
            for key in self.cache:
                if (
                    self.cache[key] is not None
                    and self.get_window(self.data[key].get_timeout(), self.edit[key])
                    < time.time()
                ):

                    assert self.cache[key].get_timeout() > self.data[key].get_timeout()
                    self.data[key] = self.cache[key]
                    self.edit[key] = time.time()
                    self.send_msg(key, self.data[key])
                    self.cache[key] = None

            self.evt.clear()

    def get_data(self, key: str) -> DataTTL:
        """Get value at key from library

        Args:
            key (str): Key

        Returns:
            DataWithTTL: Value

        Raises:
            KeyError: If key not found
        """
        return self.data[key]

    def has(self, key: str) -> bool:
        """See if library has active key

        Args:
            key (str): Key value

        Returns:
            bool: True if has active
        """
        return key in self.data and self.data[key].get_value_or_null() is not None

    def has_or_expired(self, key: str) -> bool:
        """See if library has key, independent of expiration

        Args:
            key (str): Key

        Returns:
            bool: True if exists
        """
        return key in self.data
