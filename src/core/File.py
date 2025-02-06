import struct
import os, sys
import asyncio

sys.path.append(os.path.join(os.path.dirname(__file__), "../../"))

import hashlib

from src.util.util import (
    and_bytes,
    compress_str_to_bytes,
    decompress_bytes_to_str,
    encode_to_base32,
    join_paths,
    not_bytes,
    or_bytes,
    pad_bytes,
)
import src.communications.main_pb2 as pb_base
import src.communications.main_pb2_grpc as pb

import logging


logger = logging.getLogger(__name__)
TYPE_FILE = 1
TYPE_IO = 2
TYPE_DIR = 3

# Length limited to 1MB


class FileManager:
    def __init__(self, file_save_dir):
        self.files_hosted: dict[bytes, bytes] = {}
        self.files_hosted_objects: dict[bytes, "HostedFile"] = {}
        self.file_save_dir = file_save_dir

    def is_file_hosted(self, key: bytes):
        return key in self.files_hosted

    def fetch_file(
        self, key: bytes, local_file_identifier: bytes = b"", process_id: bytes = b""
    ):
        current = self.files_hosted[key]
        if current == b"" and local_file_identifier == b"":
            # not currently in use.
            if len(process_id) != 2:
                logger.warning(f"FILE - Missing process_id")
                raise ValueError("Missing process_id on file object handler")
            new_id = os.urandom(16) + process_id
            self.files_hosted[key] = new_id
            file = self.files_hosted_objects[key]
            file.local_identifier = new_id
            return file

        if current == local_file_identifier:
            file = self.files_hosted_objects[key]
            file.local_identifier = current
            return file

        logger.debug(f"FILE - Already in use file:{key.hex()} handler:{current.hex()}")
        raise ValueError("Already in use!")

    def close_file(self, key: bytes, local_file_identifier: bytes):
        current = self.files_hosted[key]
        if current == b"":
            raise ValueError("Already closed!")

        if current != local_file_identifier:
            raise ValueError("Incorrect handler code")

        self.files_hosted[key] = b""
        file = self.files_hosted_objects[key]
        file.local_identifier = b""
        return file

    def host_file(self, file: "HostedFile"):
        if file.get_key() in self.files_hosted:
            return

        self.files_hosted[file.get_key()] = b""
        file.local_filepath = self.file_save_dir
        self.files_hosted_objects[file.get_key()] = file
        file.create()


class FileFactory:
    def __init__(self, plugboard, loop, process_id):
        self.plugboard = plugboard
        self.loop = loop
        self.process_id = process_id

    def File(self, userID: bytes, filepath: str) -> "File":
        return File(userID, filepath, self.plugboard, self.loop, self.process_id)


class File:
    def __init__(self, userID: bytes, filepath: str, plugboard, loop, process_id):
        self.hf = HostedFile(userID, filepath)
        self.plugboard = plugboard
        self.loop = loop
        self.process_id = process_id

    def create(self, overwrite: bool = False, timeout=0.5):
        future = asyncio.run_coroutine_threadsafe(
            self.plugboard.file_create(self.hf), loop=self.loop
        )
        return future.result(timeout)

    def open(self, timeout=0.5):
        future = asyncio.run_coroutine_threadsafe(
            self.plugboard.file_open(self.hf, self.process_id), loop=self.loop
        )
        self.hf = future.result(timeout)
        if self.hf is None:
            raise ValueError("File does not exist! Try creating first")
        logger.debug(f"FILE - Received handler: {self.hf.get_local_identifier().hex()}")

    def read(self, size=-1, timeout=0.5):
        future = asyncio.run_coroutine_threadsafe(
            self.plugboard.file_read(self.hf, self.process_id, size), loop=self.loop
        )
        return future.result(timeout)

    def write(self, data: bytes, timeout=0.5):
        future = asyncio.run_coroutine_threadsafe(
            self.plugboard.file_write(self.hf, self.process_id, data), loop=self.loop
        )
        return future.result(timeout)

    def seek(self, offset: int, whence=os.SEEK_SET, timeout=0.5):
        future = asyncio.run_coroutine_threadsafe(
            self.plugboard.file_seek(self.hf, self.process_id, offset, whence),
            loop=self.loop,
        )
        return future.result(timeout)

    def close(self, timeout=0.5):
        future = asyncio.run_coroutine_threadsafe(
            self.plugboard.file_close(self.hf, self.process_id), loop=self.loop
        )
        return future.result(timeout)


class HostedFile:
    def __init__(self, userID: bytes, filepath: str):
        self.userID = userID
        if filepath[0] == "/":
            filepath = filepath[1:]
        self.filepath = compress_str_to_bytes(filepath)
        self.filepath = pad_bytes(self.filepath, 4)
        self.mode = TYPE_FILE  # three bits!

        self.local_file_object = None
        self.local_filepath = None
        self.length = 0
        self.end_of_file_pos = 0
        self.local_identifier = b""

    def get_local_identifier(self):
        return self.local_identifier

    def get_key(self):
        # set three bits to zero.
        mode_mask = b"\xFF\xFF\xFF\xFF\x1F\xFF\xFF\xFF"

        out = self.userID + self.filepath
        out = and_bytes(out, mode_mask)
        # print(out.hex(sep=" "))

        if self.mode == TYPE_FILE:
            mode_bin = b"\x00\x00\x00\x00\x20\x00\x00\x00"  # 001
        elif self.mode == TYPE_IO:
            mode_bin = b"\x00\x00\x00\x00\x40\x00\x00\x00"  # 010
        elif self.mode == TYPE_DIR:
            mode_bin = b"\x00\x00\x00\x00\x60\x00\x00\x00"  # 011
        else:
            mode_bin = b"\x00\x00\x00\x00\x80\x00\x00\x00"  # 100
            # mode_bin = b"\x00\x00\x00\x00\xA0\x00\x00\x00"  # 101
            # mode_bin = b"\x00\x00\x00\x00\xC0\x00\x00\x00"  # 110
            # mode_bin = b"\x00\x00\x00\x00\xE0\x00\x00\x00"  # 111
        # print(mode_bin.hex(sep=" "))
        out = or_bytes(mode_bin, out)
        return out

    @classmethod
    def from_key(cls, key):
        user = key[0:4]
        mode_mask = b"\xFF\xFF\xFF\xFF\x1F\xFF\xFF\xFF"

        mode = and_bytes(key, not_bytes(mode_mask))
        mode = mode[4]
        if mode == 0x20:
            mode_set = TYPE_FILE
        elif mode == 0x40:
            mode_set = TYPE_IO
        elif mode == 0x60:
            mode_set = TYPE_DIR
        else:
            raise ValueError("Invalid key")

        name_bin = and_bytes(key, mode_mask)
        name = decompress_bytes_to_str(name_bin[4:])

        c = cls(user, name)
        c.mode = mode_set
        return c

    def create(self, overwrite: bool = False):
        # issue a request to the file holder.
        key = self.get_key()
        # hash_obj = hashlib.sha256() # use sha256 or base32
        # hash_obj.update(key)
        # bin_blob = hash_obj.hexdigest()

        bin_blob = encode_to_base32(key)
        assert self.local_filepath is not None
        filepath = join_paths(self.local_filepath, bin_blob + ".stg")
        if os.path.isfile(filepath) and not (overwrite):
            raise ValueError("HostedFile already found.")

        logger.debug(f"FILE - Create {filepath} - key: {key.hex()}")

        self.local_file_object = open(filepath, "w+b")  # type: ignore
        self.local_file_object.close()  # type: ignore
        self.local_file_object = None  # touch file.
        # self.length = 0
        # self.end_of_file_pos = 0

    def open(self):
        # issue a request to the file holder.
        if self.local_file_object is not None:
            return
        key = self.get_key()
        # hash_obj = hashlib.sha256() # use sha256 or base32
        # hash_obj.update(key)
        # bin_blob = hash_obj.hexdigest()

        bin_blob = encode_to_base32(key)

        filepath = join_paths(self.local_filepath, bin_blob + ".stg")
        if not (os.path.isfile(filepath)):
            raise ValueError("HostedFile not found. Try create() first")

        logger.debug(f"FILE - Open {filepath} - key: {key.hex()}")
        self.local_file_object = open(filepath, "r+b")  # type: ignore

    def read(self, size=-1):
        if self.local_file_object is None:
            raise ValueError()

        logger.debug(f"FILE - Read {self.get_key()}")
        return self.local_file_object.read(size)

    def write(self, data: bytes):
        if self.local_file_object is None:
            raise ValueError()

        logger.debug(f"FILE - Write {self.get_key().hex()}")
        l = self.local_file_object.write(data)

    def seek(self, offset: int, whence=os.SEEK_SET):
        if self.local_file_object is None:
            raise ValueError()

        logger.debug(f"FILE - Seek {self.get_key()}")
        return self.local_file_object.seek(offset, whence)

    def tell(self):
        if self.local_file_object is None:
            raise ValueError()

        logger.debug(f"FILE - Tell {self.get_key()}")
        return self.local_file_object.tell()

    def close(self):
        if self.local_file_object is None:
            return
        self.local_file_object.close()
        self.local_file_object = None
        logger.debug(f"FILE - Close {self.get_key()}")

    def get_pb(self):
        prev = self.local_file_object.tell()
        self.local_file_object.seek(0, os.SEEK_END)
        length = self.local_file_object.tell()
        self.local_file_object.seek(0, os.SEEK_SET)

        if length > 2**21 - 1:
            raise ValueError("HostedFile too big! 2 MB max")

        pb = pb_base.HostedFile(length=length, data=self.read())
        self.local_file_object.seek(prev, os.SEEK_SET)  # go back.
        return pb

    @classmethod
    def load_from_pb(cls, key: bytes, pb: pb_base.File, overwrite=False):
        out = cls.from_key(key)
        out.create(overwrite)
        out.write(pb.data)
        out.close()
        return out

    def local_load_from_pb(self, pb: pb_base.File, overwrite=False):
        self.close()
        self.create(overwrite)
        self.write(pb.data)
        self.close()


# f = HostedFile(b"User", "/hello")
# k = f.get_key()
# print(k.hex(sep=" "))

# f.create(overwrite=True)
# f.write(b"Hello!")
# f.seek(0)
# print(f.read())
# f.close()

# g = HostedFile.from_key(k)
# g.open()
# print(g.read())
# pb_info = g.get_pb()
# g.close()

# bin_str = pb_info.SerializeToString()
# print(bin_str)

# new_file = HostedFile.load_from_pb(
#     k, pb_base.HostedFile.FromString(bin_str), overwrite=True
# )
# new_file.open()
# print(new_file.read())
# new_file.close()
