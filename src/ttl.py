
import time
from typing import Dict, Optional, Union

class DataWithTTL():
    def __init__(self, data : any, timeout : float, suppress_error : bool = False):
        """Initiate a simple data object with Time-To-Live. Supposed to be immutable.

        Args:
            data (any): Data to store
            timeout (float): timeout in UNIX timestamp.
            suppress_error (bool): Set to true to ignore ValueError on creation

        Raises:
            ValueError: If timeout is in the past, raise ValueError.
        """
        self.__data = data
        self.__timeout = timeout
        self.__time_created = time.time()
        if(not(suppress_error) and self.__timeout < self.__time_created):
            raise ValueError("Timeout in the past!")
    
    def get_value(self) -> any:
        """Get value stored

        Raises:
            ValueError: If past TTL, throw exception.

        Returns:
            any: Data stored.
        """
        if(self.__timeout > time.time()):
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

    
    def get_value_or_null(self) -> Optional[any]:
        """Get value stored, or return None if past TTL.

        Returns:
            Optional[any]: Data stored or None if past TTL.
        """
        if(self.__timeout > time.time()):
            return self.__data
        else:
            return None
    
    # def __repr__(self):
    #     val = self.get_value()
    #     valid = self.__timeout > time.time()
    #     if(valid):
    #         return f"{val} - Expires at: {self.__timeout}"
    #     else:
    #         return f"{val} - EXPIRED. Expired at: {self.__timeout}"

# class HashmapTTL():
#     pass        

# class HashmapTTL():
#     def __init__(self, data : Union[Dict[str, DataWithTTL] | HashmapTTL]):
#         """Either import a dictionary with DataTTL pairs, or another HashmapTTL

#         Args:
#             data (Union[Dict[str, DataWithTTL]  |  HashmapTTL]): Imported data
#         """
#         if(isinstance(data,HashmapTTL)):
#             self.data = data.data 
#         else:
#             self.data = data

#     def get(self, key):
#         if(not(key in self.data)):
#             return None
        
#         val = self.data[key].get_value_or_null()
#         if(val is not None):
#             return val 
    
#     def add(self, key, value, timeout)
    
#     def __getitem__(self, key):
#         return self.get(key)
    
#     def __iter__(self):
#         return self.data
        

# Testing script.

if __name__ == "__main__":
    value = DataWithTTL("apple", time.time() + 4)
    for x in range(6):
        time.sleep(1)
        a = value.get_value_or_null()
        assert (x < 4 or a is None)
