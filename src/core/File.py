import struct
import os, sys
import asyncio

import dill


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
        self.monitor_files_hosted: dict[bytes, bytes] = {}
        self.files_hosted_objects: dict[bytes, "HostedFile"] = {}
        self.monitor_files_hosted_objects: dict[bytes, "HostedFile"] = {}
        self.file_save_dir = file_save_dir
        self.file_monitors: dict[bytes, bytes] = {}  # gives monitor peerID

    def is_file_hosted(self, key: bytes, is_monitor=False):
        if is_monitor:
            return key in self.monitor_files_hosted
        else:
            return key in self.files_hosted

    def get_monitor(self, file: "HostedFile"):
        return self.file_monitors.get(file.get_key())

    def fetch_file(
        self,
        key: bytes,
        local_file_identifier: bytes = b"",
        process_id: bytes = b"",
        direct_access=False,
        is_monitor=False,
    ):
        # pass through on monitor. Monitor isn't "opening" a new connection.
        if is_monitor or direct_access:
            if is_monitor:
                file = self.monitor_files_hosted_objects[key]
                file.local_identifier = local_file_identifier
                self.monitor_files_hosted[key] = local_file_identifier
            else:
                file = self.files_hosted_objects[key]
                file.local_identifier = local_file_identifier
                self.files_hosted[key] = local_file_identifier
            return file, self.file_monitors.get(key)

        # no longer monitor...
        current = self.files_hosted[key]
        if current == b"" and local_file_identifier == b"":
            # not currently in use.
            if len(process_id) != 2:
                logger.warning(f"FILE - Missing process_id")
                raise ValueError("Missing process_id on file object handler")
            new_id = os.urandom(16) + process_id
            logger.info(f"FILE - File opened {key.hex()} handler:{new_id.hex()}")
            self.files_hosted[key] = new_id
            file = self.files_hosted_objects[key]
            file.local_identifier = new_id
            return file, self.file_monitors.get(key)

        if current == local_file_identifier:
            file = self.files_hosted_objects[key]
            file.local_identifier = current
            return file, self.file_monitors.get(key)

        logger.debug(f"FILE - Already in use file:{key.hex()} handler:{current.hex()}")
        # raise KeyboardInterrupt
        raise ValueError("Already in use!")

    def close_file(self, key: bytes, local_file_identifier: bytes, is_monitor=False):
        if is_monitor:
            current = self.monitor_files_hosted[key]
        else:
            current = self.files_hosted[key]

        if current == b"":
            raise ValueError("Already closed!")

        if current != local_file_identifier:
            raise ValueError("Incorrect handler code")

        if is_monitor:
            self.monitor_files_hosted[key] = b""
            file = self.monitor_files_hosted_objects[key]
        else:
            self.files_hosted[key] = b""
            file = self.files_hosted_objects[key]
        file.local_identifier = b""
        return file

    def host_file(
        self, file: "HostedFile", monitor_peer: bytes, is_monitor=False, contents=b""
    ):
        if (file.get_key() in self.files_hosted) and not (is_monitor):
            return
        if (file.get_key() in self.monitor_files_hosted) and is_monitor:
            return

        file.is_monitor = is_monitor

        if is_monitor:
            self.monitor_files_hosted[file.get_key()] = b""
            file.local_filepath = self.file_save_dir
            self.monitor_files_hosted_objects[file.get_key()] = file
            file.create(contents=contents)
        else:
            self.files_hosted[file.get_key()] = b""
            file.local_filepath = self.file_save_dir
            self.files_hosted_objects[file.get_key()] = file
            file.create(contents=contents)
            self.file_monitors[file.get_key()] = monitor_peer

    def update_monitor(self, file: "HostedFile", monitor_peer: bytes):
        self.file_monitors[file.get_key()] = monitor_peer

    def remove_monitor(self, file: "HostedFile"):
        del self.monitor_files_hosted[file.get_key()]
        del self.monitor_files_hosted_objects[file.get_key()]
        file.local_filepath = self.file_save_dir
        file.is_monitor = True
        file.delete()

    def remove_hosted_file(self, file: "HostedFile"):
        del self.file_monitors[file.get_key()]
        del self.files_hosted[file.get_key()]
        del self.files_hosted_objects[file.get_key()]
        file.local_filepath = self.file_save_dir
        file.is_monitor = False
        file.delete()

    def fetch_contents(self, file: "HostedFile", is_monitor=False):
        file.is_monitor = is_monitor
        if is_monitor:
            if file.get_key() not in self.monitor_files_hosted:
                return None
            file.open()
            out = file.read()
            file.close()
            return out
        else:
            if file.get_key() not in self.files_hosted:
                return None
            file.open()
            out = file.read()
            file.close()
            return out


class FileFactory:
    def __init__(self, plugboard, loop, process_id, engine_id):
        self.plugboard = plugboard
        self.loop = loop
        self.process_id = process_id
        self.engine_id = engine_id

    def File(self, userID: bytes, filepath: str) -> "File":
        return File(userID, filepath, self.plugboard, self.loop, self.process_id)

    def File_Import(self, b: bytes) -> "File":
        raw = dill.loads(b)
        hf = HostedFile.from_key(raw[0])
        proc = raw[1]
        local_id = raw[2]
        hf.local_identifier = local_id
        f = File(b"", "a", self.plugboard, self.loop, proc)
        f.hf = hf
        return f


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

    def export(self):
        return dill.dumps(
            (self.hf.get_key(), self.process_id, self.hf.get_local_identifier())
        )


class HostedFile:
    def __init__(self, userID: bytes, filepath: str, is_monitor=False, mode=TYPE_FILE):
        self.userID = userID
        if filepath[0] == "/":
            filepath = filepath[1:]

        if mode == TYPE_FILE:
            self.filepath = compress_str_to_bytes(filepath)
            self.filepath = pad_bytes(self.filepath, 4)
        if mode == TYPE_IO:
            # io_host_type = 'tty'
            # /dev/tty00102
            # io_host_type = self.filepath[5:8]
            number = filepath[7:]  # skips the '/'
            number_bytes = int.to_bytes(int(number), 4, "big")
            self.filepath = pad_bytes(number_bytes, 4)

        self.mode = mode  # three bits!

        self.local_file_object = None
        self.local_filepath = None
        self.length = 0
        self.end_of_file_pos = 0
        self.local_identifier = b""
        self.is_monitor = is_monitor

    def get_filepath(self) -> str:
        if self.mode == TYPE_FILE:
            return decompress_bytes_to_str(self.filepath)
        elif self.mode == TYPE_IO:
            return f"/dev/tty{int.from_bytes(self.filepath,'big')}"
        return ""

    def get_user(self) -> bytes:
        return self.userID

    def get_local_identifier(self) -> bytes:
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

        if mode_set == TYPE_FILE:
            name = decompress_bytes_to_str(name_bin[4:])
        elif mode_set == TYPE_IO:
            name = f"/dev/tty{int.from_bytes(name_bin[4:],'big')}"

        c = cls(user, name, mode=mode_set)
        c.mode = mode_set
        return c

    def create(self, overwrite: bool = False, contents=b""):
        assert isinstance(contents, bytes)
        # issue a request to the file holder.
        key = self.get_key()
        # hash_obj = hashlib.sha256() # use sha256 or base32
        # hash_obj.update(key)
        # bin_blob = hash_obj.hexdigest()

        bin_blob = encode_to_base32(key)
        assert self.local_filepath is not None

        if self.is_monitor:
            ending = ".stm"
        else:
            ending = ".stg"
        filepath = join_paths(self.local_filepath, bin_blob + ending)

        if os.path.isfile(filepath) and not (overwrite):
            raise ValueError("HostedFile already found.")

        logger.debug(f"FILE - Create {filepath} - key: {key.hex()}")

        self.local_file_object = open(filepath, "w+b")  # type: ignore
        if contents != b"":
            self.local_file_object.write(contents)
        self.local_file_object.close()  # type: ignore
        self.local_file_object = None  # touch file.
        # self.length = 0
        # self.end_of_file_pos = 0

    def delete(self):
        key = self.get_key()
        bin_blob = encode_to_base32(key)
        assert self.local_filepath is not None
        if self.is_monitor:
            ending = ".stm"
        else:
            ending = ".stg"
        filepath = join_paths(self.local_filepath, bin_blob + ending)
        if os.path.isfile(filepath):
            os.unlink(filepath)
        else:
            logger.warning("FILE - Delete called on nonexistent file!")

    def open(self):
        # issue a request to the file holder.
        if self.local_file_object is not None:
            return
        assert self.local_filepath is not None
        key = self.get_key()
        # hash_obj = hashlib.sha256() # use sha256 or base32
        # hash_obj.update(key)
        # bin_blob = hash_obj.hexdigest()

        bin_blob = encode_to_base32(key)

        if self.is_monitor:
            ending = ".stm"
        else:
            ending = ".stg"
        filepath = join_paths(self.local_filepath, bin_blob + ending)
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

    def set_contents(self, contents: bytes):
        self.create(overwrite=True)
        self.open()
        self.write(contents)
        self.close()

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
