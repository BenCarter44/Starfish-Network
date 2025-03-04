# Register tasks (hash: name, condition)
import asyncio
import hashlib
import json
import marshal
import struct
import copy
import datetime
import functools
import time
from typing import Any, Optional, Callable, cast
import jsonpickle
from typing_extensions import Self
import dill  # type: ignore
import uuid
import logging
import grpc
import sys, os


sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
try:
    from src.util.util import and_bytes, pad_bytes
    from src.core.File import FileFactory
    from src.core.io_host import IOFactory
except:
    from util.util import and_bytes, pad_bytes
    from core.File import FileFactory
    from src.core.io_host import IOFactory


try:
    import communications.primitives_pb2 as pb_p
except:
    from ..communications import primitives_pb2 as pb_p


class StarProcess:
    def __init__(self, user_id: bytes, process_id: bytes):
        self.user_id = pad_bytes(user_id, 4)
        self.process_id = pad_bytes(process_id, 2)
        self.task_list: set[StarTask] = set()

    # list of task identifiers.
    # requires user ID.

    def to_bytes(self) -> bytes:
        """Serialize object to bytes

        Returns:
            bytes: StarProcess in bytes
        """
        return self.to_pb().SerializeToString()

    def to_pb(self) -> pb_p.Process:
        """Serialize object to Protobuf object

        Returns:
            pb_p.Process: Protobuf Process object
        """
        return pb_p.Process.FromString(self.get_all_task_bytes())

    @classmethod
    def from_pb(cls, pb):
        """Create a StarProcess from a Protobuf Process object

        Args:
            pb (Process protobuf object)

        Raises:
            NotImplementedError: Not implemented!
        """
        raise NotImplementedError

    @classmethod
    def from_bytes(cls, b: bytes) -> "StarProcess":
        """Create object from bytes

        Args:
            b (bytes): Bytes of process

        Returns:
            StarProcess: Return a StarProcess object
        """
        pb = pb_p.Process.FromString(b)
        task_list = dill.loads(pb.task_data)

        task_list_new = set()
        for i, task_b in task_list.items():
            task = StarTask.from_bytes(task_b)
            task_list_new.add(task)

        proc = cls(pb.user, pb.process_id)
        proc.task_list = task_list_new
        return proc

    def add_task(self, i: "StarTask"):
        """Associate a task to a process

        Args:
            i (StarTask): StarTask to associate to the process
        """
        assert type(i) == type(cast(StarTask, i))
        # assert isinstance(i, StarTask)
        i.attach_to_process(self)
        self.task_list.add(i)

    def get_tasks(self) -> set["StarTask"]:
        """Get tasks associated with the process

        Returns:
            set[StarTask]: Tasks associated with the process
        """
        return self.task_list

    def get_all_task_bytes(self) -> bytes:
        out = {}
        for task in self.task_list:
            out[task.get_id()] = task.to_bytes_with_callable()

        task_data = dill.dumps(out)

        pb = pb_p.Process(
            user=self.user_id, process_id=self.process_id, task_data=task_data
        )
        return pb.SerializeToString()

    def get_id(self) -> bytes:
        # first 32 bytes are routing
        # second 32 bytes are user bytes
        # third 32 bytes are process ID bytes
        # fourth 32 bytes are task bytes
        custom = self.user_id + self.process_id + pad_bytes(b"", 2)  # 0 for task_id.
        # custom_bytes = pad_bytes(custom, 32)
        # return custom_bytes + self.user_id + self.process_id + self.name
        return custom

    def get_user(self) -> bytes:
        return self.user_id


class NodeSyscall:
    def __init__(self, node, loop):
        self.node = node
        self.loop = loop

    def get_peerID(self):
        t = asyncio.run_coroutine_threadsafe(self.node.get_peerID(), self.loop)
        return t.result()

    def start_program(self, program: "Program", user_id: bytes, extra={}):
        t = asyncio.run_coroutine_threadsafe(
            self.node.start_program(program, user_id, extra), self.loop
        )
        return t.result()

    def get_file_list(self):
        return self.node.file_list(True)

    def get_io_list(self):
        return self.node.io_list(True)


class StarTask:
    def __init__(
        self, user_id: bytes, process_id: bytes, task_id: bytes, pass_id=False
    ):
        self.user_id = pad_bytes(user_id, 4)
        self.process_id = pad_bytes(process_id, 2)
        self.task_id = pad_bytes(task_id, 2)
        self.callable = b""
        self.nice_name = ""
        self.runtime_data: Optional[dict[str, bytes]] = None
        self.pass_id = pass_id

        self.hold_past_event = None
        self.hold_past_event_pre = None
        self.hold_process: Optional[StarProcess] = None
        self.monitor = b""

        self.plugboard_callback = None
        self.loop_callback = None  # struct for file factory
        self.node_callback = None

    def get_user(self) -> bytes:
        return self.user_id

    def get_node_kernel(self) -> NodeSyscall:
        return NodeSyscall(self.node_callback, self.loop_callback)

    def to_bytes(self) -> bytes:
        """Serialize StarTask to bytes

        Returns:
            bytes: bytes of the object
        """
        return self.to_pb().SerializeToString()

    def to_pb(self, include_callable=False) -> pb_p.TaskIdentifier:
        """Serialize object to Protobuf

        Args:
            include_callable (bool, optional): Include callable function. Defaults to False.

        Returns:
            pb_p.TaskIdentifier: Protobuf object
        """
        if self.callable != b"" and include_callable:
            c = dill.dumps((self.callable, self.runtime_data), fmode=dill.FILE_FMODE)
        else:
            c = b""

        return pb_p.TaskIdentifier(
            user_id=self.user_id,
            process_id=self.process_id,
            task_id=self.task_id,
            callable_data=c if include_callable else b"",
            pass_id=self.pass_id,
            monitor_peer=self.monitor,
        )

    def to_bytes_with_callable(self) -> bytes:
        """Serialize to bytes including callable

        Returns:
            bytes: Bytes
        """
        return self.to_pb(True).SerializeToString()

    @classmethod
    def from_pb(cls, pb: pb_p.TaskIdentifier) -> "StarTask":
        """Create StarTask from protobuf object

        Args:
            pb (pb_p.TaskIdentifier): Protobuf object

        Returns:
            StarTask: Task object
        """
        out = cls(pb.user_id, pb.process_id, pb.task_id, pb.pass_id)

        if pb.callable_data != b"":
            c, r = dill.loads(pb.callable_data)
        else:
            c = b""
            r = {}
        out.callable = c
        out.runtime_data = r
        out.monitor = pb.monitor_peer
        # logger.debug(f"From PB: {out.callable}")
        return out

    @classmethod
    def from_bytes(cls, b: bytes):
        ti = pb_p.TaskIdentifier()
        ti = ti.FromString(b)
        return cls.from_pb(ti)

    def from_bytes_local(self, b):
        """Same as from_bytes but overwrites the object

        Args:
            b (bytes): The bytes of the object
        """
        ti = pb_p.TaskIdentifier()
        ti = ti.FromString(b)
        r = self.from_pb(ti)
        self.__init__(r.user_id, r.process_id, r.task_id)
        self.pass_id = ti.pass_id
        self.callable = r.callable
        self.runtime_data = r.runtime_data

    def attach_to_process(self, process_object: StarProcess):
        self.process_id = process_object.process_id
        self.user_id = process_object.user_id

    def attach_to_process_task(self, process_object: "StarTask"):
        self.process_id = process_object.process_id
        self.user_id = process_object.user_id

    def set_callable(self, callable):
        self.callable = callable

    def get_callable(self):
        return self.callable

    def clear_callable(self):
        self.callable = None

    def get_file_factory(self):
        return FileFactory(
            self.plugboard_callback,
            self.loop_callback,
            self.process_id,
            self.plugboard_callback.my_addr,
        )

    def get_io_factory(self):
        return IOFactory(
            self.plugboard_callback,
            self.loop_callback,
            self.process_id,
            self.plugboard_callback.my_addr,
        )

    def get_id(self):
        # first 32 bytes are routing
        # second 32 bytes are user bytes
        # third 32 bytes are process ID bytes
        # fourth 32 bytes are task bytes
        custom = self.user_id + self.process_id + self.task_id
        # custom_bytes = pad_bytes(custom, 32)
        # return custom_bytes + self.user_id + self.process_id + self.name
        return custom

    def get_process_id(self):
        # Keep first 6 bytes
        mask = b"\xFF\xFF\xFF\xFF\xFF\xFF\x00\x00"
        process_id = and_bytes(self.get_id(), mask)
        return process_id

    def __hash__(self):
        return hash(self.get_id())

    def __eq__(self, other):
        if isinstance(other, StarTask):
            return other.get_id() == self.get_id()
        return False

    def __getstate__(self):  # for pickling
        return {"data": self.to_bytes_with_callable()}

    def __setstate__(self, state):  # for unpickling.
        # logger.debug(state)
        self.from_bytes_local(state["data"])

    def set_nice_name(self, nice_name: str):
        self.nice_name = nice_name

    def __repr__(self):
        hx = self.get_id()
        # use md5 to make it shorter
        hx_nice = hx.hex()
        return f"<{self.nice_name} {hx_nice}>"


class StarAddress:
    """Event Struct"""

    def __init__(self, string: str):
        """Hold values that get passed from one task to another

        Args:
            a (Any, optional): A value. Defaults to 0.
            b (Any, optional): B value. Defaults to 0.
        """
        self.protocol = string.split("://", 1)[0]
        self.host = string[len(self.protocol) + 3 :].split(":", 1)[0]
        self.port = int(string.split(":")[-1])
        self.protocol = self.protocol.encode("utf-8")
        self.host = self.host.encode("utf-8")
        self.port = str(self.port).encode("utf-8")
        self.keep_alive = None

    def to_bytes(self) -> bytes:
        return self.to_pb().SerializeToString()

    def to_pb(self) -> pb_p.TransportAddress:
        return pb_p.TransportAddress(
            protocol=self.protocol, host=self.host, port=self.port
        )

    @classmethod
    def from_pb(cls, pb):
        out = cls("dummy://0:0")
        out.protocol = pb.protocol
        out.host = pb.host
        out.port = pb.port
        return out

    @classmethod
    def from_bytes(cls, b):
        ti = pb_p.TransportAddress()
        ti = ti.FromString(b)
        return cls.from_pb(ti)

    def get_channel(self) -> grpc.aio.Channel:
        string = f"{self.host.decode('utf-8')}:{self.port.decode('utf-8')}"
        if self.keep_alive is None:
            raise ValueError("Please attach to KeepAlive Management first")
        return self.keep_alive.get_channel(string)

    def set_keep_alive(self, kp):
        self.keep_alive = kp

    def get_string_channel(self):
        string = f"{self.host.decode('utf-8')}:{self.port.decode('utf-8')}"
        return string


logger = logging.getLogger(__name__)


IS_ENGINE = False
BINDINGS: dict[str, Callable] = {}

ZERO_8 = b"\x00\x00\x00\x00\x00\x00\x00\x00"


class Event:
    """Event Struct"""

    def __init__(self, data={}):
        """Hold values that get passed from one task to another

        Args:
            a (Any, optional): A value. Defaults to 0.
            b (Any, optional): B value. Defaults to 0.
        """
        self.data = data
        self.system = None
        self.target = None
        self.origin = None
        self.origin_previous = None
        self.is_target_conditional = False  # used for compiler only
        self.is_checkpoint = True

        self.owned_user_id: Optional[bytes] = None
        self.owned_process_id: Optional[bytes] = None
        self.nonce = 0
        self.target_string = ""

    def to_bytes(self) -> bytes:
        return self.to_pb().SerializeToString()

    def to_pb(self) -> pb_p.Event:
        task_to = self.target
        if self.target is None:
            task_to = StarTask(b"", b"", b"")

        event_origin = self.origin
        if self.origin is None:
            event_origin = b""
        else:
            logger.debug(f"TASK - {self.origin.target}")
            logger.debug(f"TASK - {self.target}")
            self.origin.origin = None  # No recursion.
            logger.debug(f"TASK - {self.origin.target}")
            event_origin = self.origin.to_bytes()

        event_origin_previous = self.origin_previous
        if self.origin_previous is None:
            event_origin_previous = b""
        else:
            self.origin_previous.origin = None  # No recursion.
            event_origin_previous = self.origin_previous.to_bytes()

        evt_out = pb_p.Event(
            task_to=task_to.to_pb(),
            task_from=event_origin,
            task_pre=event_origin_previous,
            data=dill.dumps(self.data, fmode=dill.FILE_FMODE),
            system_data=dill.dumps(self.system, fmode=dill.FILE_FMODE),
            nonce=self.nonce,
            is_checkpoint=self.is_checkpoint,
            target_string=self.target_string,
        )

        return evt_out

    def __hash__(self):
        # A Event is the same as another event if the NONCE and TARGET are the same!
        dt = (self.target.get_id(), self.nonce)
        return hash(dt)

    def __eq__(self, other):
        if isinstance(other, Event):
            return (
                self.target.get_id() == other.target.get_id()
                and other.nonce == self.nonce
            )
        return False

    @classmethod
    def from_pb(cls, pb):
        data = dill.loads(pb.data)
        system = dill.loads(pb.system_data)
        task_to = pb.task_to
        evt_from = pb.task_from
        evt_pre = pb.task_pre
        if evt_from == b"":
            evt_from = None
        else:
            evt_from = cls.from_bytes(evt_from)

        if evt_pre == b"":
            evt_pre = None
        else:
            evt_pre = cls.from_bytes(evt_pre)

        out = cls(data)
        out.system = system
        out.target = StarTask.from_pb(task_to)
        out.origin = evt_from
        out.origin_previous = evt_pre
        out.nonce = pb.nonce
        out.is_checkpoint = pb.is_checkpoint
        out.target_string = pb.target_string
        return out

    @classmethod
    def from_bytes(cls, b):
        ti = pb_p.Event.FromString(b)
        return cls.from_pb(ti)

    def clear_system(self) -> None:
        """Clear out system parameters"""
        self.system = None

    def define_system(self) -> None:
        """Set system parameters to empty dictionary"""
        self.system = {}

    def set_target(self, target: StarTask | str) -> None:
        """Set target task of event.

        Args:
            target (str): Label for task.
        """
        try:
            i = target.get_id()  # type: ignore
            self.target = target
            # self.target_string = target
            return
        except:
            pass  # Not a StarTask .... isinstance doesn't work for some reason on programs

        target = cast(str, target)

        if target.find(":") != -1:
            raise ValueError("No colons allowed in task name!")

        task_identifier = StarTask(
            self.owned_user_id if self.owned_user_id is not None else b"",
            self.owned_process_id if self.owned_process_id is not None else b"",
            b"",
        )
        task_identifier.set_nice_name(target)
        self.target_string = target
        self.target = task_identifier

    def set_kill_target(self) -> None:
        # Tells OS that program is done!
        self.target_string = ""
        self.target = None

    def set_conditional_target(self, target: StarTask | str) -> None:
        """Set target task of event.

        Args:
            target (str): Label for task.
        """
        self.is_target_conditional = True

        if isinstance(target, StarTask):
            self.target = target
            return

        if target.find(":") != -1:
            raise ValueError("No colons allowed in task name!")

        task_identifier = StarTask(
            self.owned_user_id if self.owned_user_id is not None else b"",
            self.owned_process_id if self.owned_process_id is not None else b"",
            b"",
        )
        task_identifier.set_nice_name(target)
        self.target_string = target
        self.target = task_identifier


# class AwaitGroup:
#     """Group of AwaitEvent()"""

#     def __init__(
#         self,
#         *,
#         originating_task: StarTask,
#         return_event: Optional[Event] = None,
#         flood_time_delay=0.01,  # 1 msec
#     ):
#         """Create group of await events.

#         Args:
#             originating_task (TaskIdentifier): TaskID of origin task
#             return_event (Optional[Event], optional): Not Implemented! Fire this event when all tasks in group finish. Defaults to None.
#             flood_time_delay (float, optional): Short delay between add_event calls. Defaults to 0.001.
#         """
#         self.return_event = return_event
#         self.awaits: list[AwaitEvent] = []
#         self.origin_task = originating_task
#         self.flood_time_delay = flood_time_delay
#         if return_event is not None:
#             raise NotImplementedError(
#                 "Return event on await group not implemented yet!"
#             )

#     def add_event(self, evt: Event) -> None:
#         """Add event to group. Automatically sends out the event

#         Args:
#             evt (Event): Event to add.
#         """
#         await_evt = AwaitEvent(evt, self.origin_task)
#         time.sleep(self.flood_time_delay)  # something is wrong with the delays. TODO.
#         self.awaits.append(await_evt)

#     def wait_result_for_all(self, timeout=2.0) -> list[Event]:
#         """Wait for events in the group to finish.

#         Args:
#             timeout (float, optional): Timeout per each event in seconds. Defaults to 2.0.

#         Returns:
#             list[Event]: Returned events.
#         """

#         if not (IS_ENGINE):
#             return []

#         out: list[Event] = []
#         for x in self.awaits:
#             out.append(x.wait_for_result(timeout=timeout))

#         return out

#     def close(self):
#         """Free the await event group from engine."""
#         for x in self.awaits:
#             x.cleanup()

#     # will need override. wait()


# class AwaitEvent:
#     """Used to create events in a task while being able to track their completion."""

#     def __init__(
#         self,
#         evt: Event,
#         originating_task: StarTask,
#     ):
#         """Create Awaitable Event. Immediately sends out on creation.

#         Args:
#             evt (Event): Event
#             originating_task (TaskIdentifier): origin TaskID
#         """
#         evt.target.attach_to_process_task(originating_task)
#         self.evt = evt

#         # create trigger and place in list.

#         f = BINDINGS["create_trigger"]
#         trigger = f(originating_task)

#         # tsk = star.create_dynamic_task(f, condition=None)
#         evt.define_system()
#         evt.system["await"] = True
#         evt.system["initial"] = True
#         evt.system["previous"] = evt
#         evt.system["node"] = BINDINGS["get_node_id"]()
#         evt.system["trigger"] = trigger  # expect response.
#         evt.is_checkpoint = False

#         self.trigger = trigger
#         dispatch_event(
#             evt, originating_task
#         )  # original event. This will then send back event to dynamic task

#         # dynamic task will read the event, and then set AwaitEvent to ready()
#         #

#         # set await asyncio.event()
#         # async trigger for when event is triggered

#     def wait_for_result(self, timeout: float = 2.0) -> Event:
#         """Wait for result of event. Return returned event when done.

#         Args:
#             timeout (float, optional): Timeout to wait. Defaults to 2.0.

#         Returns:
#             Event: Returned event.
#         """
#         if not (IS_ENGINE):
#             return  # type: ignore
#         f = BINDINGS["await_trigger"]
#         return f(self.trigger, timeout=timeout)

#     def is_ready(self) -> bool:
#         """Check if event is ready.

#         Returns:
#             bool: True if ready.
#         """
#         if not (IS_ENGINE):
#             return  # type: ignore
#         f = BINDINGS["is_trigger_ready"]
#         return f(self.trigger)

#     def cleanup(self):
#         """Cleanup awaited event"""
#         if not (IS_ENGINE):
#             return  # type: ignore
#         f = BINDINGS["cleanup_trigger"]
#         return f(self.trigger)


def dispatch_event(evt: Event, originating_task: StarTask) -> None:
    """Send out event. Does not allow for checking completion. Use AwaitEvent for that.

    Args:
        evt (Event): Event to send

    Returns:
        _type_: _description_
    """
    if not (IS_ENGINE):
        return None

    # recv_event(evt)  # equiv.

    evt.owned_process_id = originating_task.process_id
    evt.owned_user_id = originating_task.user_id

    evt.target.task_id = originating_task.runtime_data[evt.target_string]

    evt.target.attach_to_process_task(originating_task)
    evt.origin = originating_task.hold_past_event
    evt.origin_previous = originating_task.hold_past_event_pre
    evt.is_checkpoint = False
    logger.info(f"TASK - {evt.target}")
    logger.info(f"TASK - SEND: {evt.data}")
    f = BINDINGS["dispatch_event"]
    return f(evt, increment=True)


# Currently global for program. --> a program is simply a list of Tasks with Callable.
task_list: set[StarTask] = set()
conditional_task_list: dict[str, list[tuple[str, str, Callable, bool]]] = {}
preview_task_list: list[tuple[str, Callable, bool]] = []


class Program:
    """A program struct"""

    def __init__(
        self,
        *,
        task_list: set[StarTask] = set(),
        read_pgrm: Optional[str] = None,
        start_event: Optional[Event] = None,
    ):
        """Create Program Object

        Args:
            task_list (Optional[dict[TaskIdentifier, Callable]], optional): Task list. Generated from decorator. Defaults to None.
            read_pgrm (Optional[str], optional): String of binary program package. Defaults to None.
            start_event (Optional[Event], optional): Initial Event When Program Loaded. Defaults to None.
        """
        self.task_list = task_list
        self.start = None
        if start_event is not None:
            self.start = start_event

        self.saved_data: dict[str, Any] = {}
        if read_pgrm is not None:
            self.read_program(read_pgrm)

    def save(self, fname: str):
        """Save program as binary program package

        Args:
            fname (str): Filename of binary program package
        """

        with open(fname, "wb") as f:
            save_data = {}
            save_data["date_compiled"] = datetime.datetime.now()  # type: ignore
            save_data["task_list"] = self.task_list  # type: ignore
            save_data["start"] = self.start  # type: ignore
            save_data["pgrm_name"] = fname  # type: ignore
            dill.dump(save_data, f, fmode=dill.FILE_FMODE, recurse=True)

        with open(fname + ".debug.json", "w") as f:
            save_data = {}
            save_data["date_compiled"] = datetime.datetime.now()  # type: ignore
            save_data["task_list"] = self.task_list  # type: ignore
            save_data["start"] = self.start  # type: ignore
            save_data["pgrm_name"] = fname  # type: ignore
            output = jsonpickle.encode(save_data)
            parsed = json.loads(output)
            json.dump(parsed, f, indent=4)

    def read_program(self, fname: str):
        """Read program from binary program package

        Args:
            fname (str): Filename of binary program package
        """
        with open(fname, "rb") as f:
            dat = dill.load(f)
            # logger.info(f"Opened program compiled on {dat['date_compiled']}")
            self.task_list = dat["task_list"]
            self.saved_data = dat
            self.start = dat["start"]


############################################################


# task_to_id: dict[str, bytes] = {}


# def setup(names: list[str]):
#     global task_to_id
#     counter = 0
#     for name in names:
#         counter_b = int.to_bytes(counter, 2, "big")
#         task_to_id[name] = counter_b
#         counter += 1
#     return task_to_id


def task(name: str, pass_task_id=False, checkpoint=True):
    """Decorator for building a task

    Args:
        name (str): Name of task. Can use in star.Event().set_target()
        condition (Optional[str], optional): Function that returns bool to select task. Defaults to None (no condition)
        pass_task_id (bool, optional): Pass TaskID when engine runs it. Defaults to False.
    """

    def wrap(func):
        # @functools.wraps(func)
        def f_wrap(*args, **kwargs):
            # func(*args, **kwargs)
            return func(
                *args, **kwargs
            )  # do not pass arguments. Do func(*args, **kwargs) if want args.

            # evt_out.target.task_id = task_to_id[name]
            # return evt_out

        # Register Task with function=wrap, name=name, condition=condition
        if name.find(":") != -1:
            raise ValueError("No colons allowed in task name!")
        # task_identifier = StarTask(b"", b"", task_to_id[name], pass_task_id)
        # task_identifier.set_nice_name(name)
        # task_identifier.set_callable(f_wrap)
        # f_wrap(Event(), StarTask(b"", b"", b"", False))
        preview_task_list.append((name, f_wrap, pass_task_id, checkpoint))

        return f_wrap

    return wrap


def conditional_task(name: str, condition: str, pass_task_id=False):
    """Decorator for building a task

    Args:
        name (str): Name of task. Can use in star.Event().set_target()
        condition (Optional[str], optional): Function that returns bool to select task. Defaults to None (no condition)
        pass_task_id (bool, optional): Pass TaskID when engine runs it. Defaults to False.
    """

    def wrap(func):
        # @functools.wraps(func)
        def f_wrap(*args, **kwargs):
            # func(*args, **kwargs)
            return func(
                *args, **kwargs
            )  # do not pass arguments. Do func(*args, **kwargs) if want args.

        # Register Task with function=wrap, name=name, condition=condition
        # create the actual tasks later under compile.
        if name.find(":") != -1:
            raise ValueError("No colons allowed in task name!")
        if name in conditional_task_list:
            conditional_task_list[name].append((name, condition, f_wrap, pass_task_id))
        else:
            conditional_task_list[name] = [(name, condition, f_wrap, pass_task_id)]
        # print(f"Registered task {name} with condition {condition}...")

        return f_wrap

    return wrap


def compile(start_event: Event) -> Program:
    """Compile star program into binary package for import into engine

    Args:
        start_event (Event): Event to fire when program loaded

    Returns:
        Program: Program Object
    """

    # do unconditional tasks first
    counter = 0
    task_to_id = {}
    task_to_checkpoint = {}
    for name, f_wrap, pass_task_id, checkpoint in preview_task_list:
        task_to_id[name] = int.to_bytes(counter, 2, "big", signed=False)
        task_to_checkpoint[name] = checkpoint
        counter += 1

    logger.debug(f"TASK - {task_to_checkpoint}")

    for name, f_wrap, pass_task_id, checkpoint in preview_task_list:
        # print(name, f_wrap)
        def edit_ti(func):
            def edit_task_id(*args, **kwargs):
                e = func(*args, **kwargs)
                # print(e.target_string, "ENGINE")
                if e.target is None:
                    logger.info("ENGINE - Kill Event")
                    return None
                if e.target_string is None:
                    logger.error(
                        "Program error: Did you forget a event.set_target()? Target unknwon. Dropping."
                    )
                    return None
                e.target.task_id = task_to_id[e.target_string]

                if e.target_string not in task_to_checkpoint:
                    e.is_checkpoint = False  # Conditional task. Mark False
                else:
                    e.is_checkpoint = task_to_checkpoint[e.target_string]
                return e

            return edit_task_id

        task_identifier = StarTask(b"", b"", task_to_id[name], pass_task_id)  # type: ignore
        task_identifier.set_nice_name(name)
        task_identifier.set_callable(edit_ti(f_wrap))
        task_list.add(task_identifier)

    # go through each task. See the condition. If multiple, create a decision event

    # unconditional tasks are all set!

    # create master decision func.
    def build_master_func(cond_str_dict):
        conditions_tmp = []
        for s, out in cond_str_dict.items():
            conditions_tmp.append((out, eval(s, {}, {})))

        def custom_decision_tree(evt, task=None):
            e = evt
            for token in conditions_tmp:
                task_id_out, lambda_condition = token
                if lambda_condition(evt):
                    e.set_target(task_id_out)
                    e.is_checkpoint = False  # no checkpoint on conditional.
                    break
            return e

        return custom_decision_tree

    counter_all = len(task_to_id)
    for name, condition_list in conditional_task_list.items():

        # create the individual tasks
        counter = 0
        condition_dict = {}  # [condition_str] = target_task.
        for cond_task_tokens in condition_list:
            c_name, condition_str, func, pass_id = cond_task_tokens

            new_name = f"{c_name}:{counter}"
            task_to_id[new_name] = int.to_bytes(counter_all, 2, "big", signed=False)
            counter_all += 1
            task_identifier = StarTask(b"", b"", task_to_id[new_name], pass_id)
            task_identifier.set_nice_name(new_name)

            def edit_ti(func):
                def edit_task_id(*args, **kwargs):
                    e = func(*args, **kwargs)
                    e.target.task_id = task_to_id[e.target_string]
                    if e.target_string not in task_to_checkpoint:
                        e.is_checkpoint = False  # Conditional task. Mark False
                    else:
                        e.is_checkpoint = task_to_checkpoint[e.target_string]
                    return e

                return edit_task_id

            task_identifier.set_callable(edit_ti(func))
            counter += 1

            task_list.add(task_identifier)
            condition_dict[condition_str] = task_identifier

        # create master task
        func = build_master_func(condition_dict)
        task_to_id[name] = int.to_bytes(counter_all, 2, "big", signed=False)
        counter_all += 1
        task_identifier = StarTask(b"", b"", task_to_id[name], pass_id)
        task_identifier.set_nice_name(name)
        task_identifier.set_callable(func)
        task_list.add(task_identifier)

    for task in task_list:
        logger.info(f"TASK - Registered: {task}")
        task.runtime_data = task_to_id

    start_event.target.task_id = task_to_id[start_event.target_string]
    start_event.is_checkpoint = True
    logger.info(f"TASK - Start: {start_event.target}")
    program = Program(task_list=task_list, start_event=start_event)
    # program.show_dependencies()
    return program
