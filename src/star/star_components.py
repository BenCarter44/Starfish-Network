# Register tasks (hash: name, condition)
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


def pad_bytes(b: bytes, l: int):
    data = bytearray(b)
    padding_byte = b"\x00"
    data = data.rjust(l, padding_byte)  # pad on MSB
    return bytes(data)


class StarProcess:
    def __init__(self, user_id: bytes, process_id: bytes):
        self.user_id = pad_bytes(user_id, 32)
        self.process_id = pad_bytes(process_id, 32)
        self.task_list = set()

    # list of task identifiers.
    # requires user ID.

    def add_task(self, i: "StarTask"):
        i.attach_to_process(self)
        self.task_list.add(i)

    def get_tasks(self):
        return self.task_list


def task_hash(task: "StarTask"):
    assert isinstance(task, StarTask)
    return task.get_id()


def pass_through_hash(b: bytes):
    return b


def parse_task_from_id(task_id: bytes):
    if len(task_id) != 32 * 4:
        return None

    user_id = task_id[0:32]
    process_id = task_id[32:64]
    name = task_id[64:96]
    custom_bytes = task_id[96:]
    custom_bytes_window = 4 * 3
    custom_bytes = custom_bytes[-custom_bytes_window:]

    version, subversion = struct.unpack(">ii", custom_bytes)

    task = StarTask(name)
    task.user_id = user_id
    task.process_id = process_id
    task.version = version
    task.subversion = subversion
    return task


class StarTask:
    def __init__(self, name: bytes, require_task_id_param=False):
        self.name = pad_bytes(name, 32)
        self.require_param = require_task_id_param  # private!
        self.process_id = pad_bytes(b"", 32)
        self.user_id = pad_bytes(b"", 32)
        self.version = 3
        self.subversion = 1
        self.nice_name = ""

        if (
            len(self.process_id) != 32
            or len(self.user_id) != 32
            or len(self.name) != 32
        ):
            logger.warn(len(self.process_id))
            logger.warn(len(self.user_id))
            logger.warn(len(self.name))
            raise ValueError("Value not padded correctly!")

        self.callable = None

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

    def get_id(self):
        # first 32 bytes are user bytes
        # second 32 bytes are process ID bytes
        # third 32 bytes are task bytes
        # fourth 32 bytes are aux

        custom = struct.pack(">ii", self.version, self.subversion)  # not param.
        custom_bytes = pad_bytes(custom, 32)
        return self.user_id + self.process_id + self.name + custom_bytes

    def __hash__(self):
        return hash(self.get_id())

    def __eq__(self, other):
        if isinstance(other, StarTask):
            return other.get_id() == self.get_id()
        return False

    def __getstate__(self):  # for pickling

        # don't recurse here.
        callable_bts = dill.dumps(self.callable, fmode=dill.FILE_FMODE, recurse=False)
        return {
            "name": self.name,
            "require_param": self.require_param,
            "process_id": self.process_id,
            "user_id": self.user_id,
            "version": self.version,
            "subversion": self.subversion,
            "nice_name": self.nice_name,
            "callable": bytes(callable_bts),
        }

    def __setstate__(self, state):  # for unpickling.
        self.name = state["name"]
        self.require_param = state["require_param"]
        self.process_id = state["process_id"]
        self.user_id = state["user_id"]
        self.version = state["version"]
        self.subversion = state["subversion"]
        self.nice_name = state["nice_name"]
        bts = state["callable"]
        self.callable = dill.loads(bts)

    def set_nice_name(self, nice_name: str):
        self.nice_name = nice_name

    def pack_for_sending(self):
        other = StarTask(self.name, self.require_param)
        other.nice_name = self.nice_name
        other.process_id = self.process_id
        other.user_id = self.user_id
        other.version = self.version
        other.subversion = self.subversion
        return other

    def __repr__(self):
        hx = self.get_id()
        # use md5 to make it shorter
        res = hashlib.md5(hx)

        return (
            f"<{self.nice_name} {res.hexdigest()}>\n{hx.hex()[0:128]}\n{hx.hex()[128:]}"
        )


logger = logging.getLogger(__name__)

# Currently global for program. --> a program is simply a list of Tasks with Callable.
task_list: set[StarTask] = set()
conditional_task_list: dict[str, list[tuple[str, str, Callable, bool]]] = {}

IS_ENGINE = False
BINDINGS: dict[str, Callable] = {}

ZERO_32 = b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"


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
        self.is_target_conditional = False  # used for compiler only

        self.original_user_id: Optional[bytes] = None
        self.original_process_id: Optional[bytes] = None

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
        if isinstance(target, StarTask):
            self.target = target
            return

        if target.find(":") != -1:
            raise ValueError("No colons allowed in task name!")

        hsh_func = hashlib.sha256()
        hsh_func.update(target.encode("utf-8"))
        task_identifier = StarTask(hsh_func.digest())
        task_identifier.set_nice_name(target)
        self.target = task_identifier

        if self.original_process_id is not None:
            self.target.process_id = self.original_process_id
        else:
            self.target.process_id = ZERO_32

        if self.original_user_id is not None:
            self.target.user_id = self.original_user_id
        else:
            self.target.user_id = ZERO_32

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

        hsh_func = hashlib.sha256()
        hsh_func.update(target.encode("utf-8"))
        task_identifier = StarTask(hsh_func.digest())
        task_identifier.set_nice_name(target)
        self.target = task_identifier

        self.target.process_id = self.original_process_id
        self.target.user_id = self.original_user_id


class AwaitGroup:
    """Group of AwaitEvent()"""

    def __init__(
        self,
        *,
        originating_task: StarTask,
        return_event: Optional[Event] = None,
        flood_time_delay=0.01,  # 1 msec
    ):
        """Create group of await events.

        Args:
            originating_task (TaskIdentifier): TaskID of origin task
            return_event (Optional[Event], optional): Not Implemented! Fire this event when all tasks in group finish. Defaults to None.
            flood_time_delay (float, optional): Short delay between add_event calls. Defaults to 0.001.
        """
        self.return_event = return_event
        self.awaits: list[AwaitEvent] = []
        self.origin_task = originating_task
        self.flood_time_delay = flood_time_delay
        if return_event is not None:
            raise NotImplementedError(
                "Return event on await group not implemented yet!"
            )

    def add_event(self, evt: Event) -> None:
        """Add event to group. Automatically sends out the event

        Args:
            evt (Event): Event to add.
        """
        await_evt = AwaitEvent(evt, self.origin_task)
        time.sleep(self.flood_time_delay)  # something is wrong with the delays. TODO.
        self.awaits.append(await_evt)

    def wait_result_for_all(self, timeout=2.0) -> list[Event]:
        """Wait for events in the group to finish.

        Args:
            timeout (float, optional): Timeout per each event in seconds. Defaults to 2.0.

        Returns:
            list[Event]: Returned events.
        """

        if not (IS_ENGINE):
            return []

        out: list[Event] = []
        for x in self.awaits:
            out.append(x.wait_for_result(timeout=timeout))

        return out

    def close(self):
        """Free the await event group from engine."""
        for x in self.awaits:
            x.cleanup()

    # will need override. wait()


class AwaitEvent:
    """Used to create events in a task while being able to track their completion."""

    def __init__(
        self,
        evt: Event,
        originating_task: StarTask,
    ):
        """Create Awaitable Event. Immediately sends out on creation.

        Args:
            evt (Event): Event
            originating_task (TaskIdentifier): origin TaskID
        """
        evt.target.attach_to_process_task(originating_task)
        self.evt = evt

        # create trigger and place in list.

        f = BINDINGS["create_trigger"]
        trigger = f(originating_task)

        # tsk = star.create_dynamic_task(f, condition=None)
        evt.define_system()
        evt.system["await"] = True
        evt.system["initial"] = True
        evt.system["previous"] = evt
        evt.system["node"] = BINDINGS["get_node_id"]()
        evt.system["trigger"] = trigger  # expect response.

        self.trigger = trigger
        dispatch_event(
            evt, originating_task
        )  # original event. This will then send back event to dynamic task

        # dynamic task will read the event, and then set AwaitEvent to ready()
        #

        # set await asyncio.event()
        # async trigger for when event is triggered

    def wait_for_result(self, timeout: float = 2.0) -> Event:
        """Wait for result of event. Return returned event when done.

        Args:
            timeout (float, optional): Timeout to wait. Defaults to 2.0.

        Returns:
            Event: Returned event.
        """
        if not (IS_ENGINE):
            return  # type: ignore
        f = BINDINGS["await_trigger"]
        return f(self.trigger, timeout=timeout)

    def is_ready(self) -> bool:
        """Check if event is ready.

        Returns:
            bool: True if ready.
        """
        if not (IS_ENGINE):
            return  # type: ignore
        f = BINDINGS["is_trigger_ready"]
        return f(self.trigger)

    def cleanup(self):
        """Cleanup awaited event"""
        if not (IS_ENGINE):
            return  # type: ignore
        f = BINDINGS["cleanup_trigger"]
        return f(self.trigger)


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

    evt.original_process_id = originating_task.process_id
    evt.original_user_id = originating_task.user_id
    evt.target.attach_to_process_task(originating_task)
    logger.info(evt.target)
    logger.info(f"SEND: {evt.data}")
    f = BINDINGS["dispatch_event"]
    return f(evt)


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


def task(name: str, pass_task_id=False):
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
        if name.find(":") != -1:
            raise ValueError("No colons allowed in task name!")
        hsh_func = hashlib.sha256()
        hsh_func.update(name.encode("utf-8"))
        task_identifier = StarTask(hsh_func.digest(), pass_task_id)
        task_identifier.set_nice_name(name)
        task_identifier.set_callable(f_wrap)

        task_list.add(task_identifier)
        logger.info(f"Registered task {name} with ID: {task_identifier.get_id()!r}")

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
        logger.info(f"Registered task {name} with condition {condition}...")

        return f_wrap

    return wrap


def compile(start_event: Event) -> Program:
    """Compile star program into binary package for import into engine

    Args:
        start_event (Event): Event to fire when program loaded

    Returns:
        Program: Program Object
    """

    # go through each task. See the condition. If multiple, create a decision event

    # unconditional tasks are all set!

    # create master decision func.
    def build_master_func(cond_str_dict):
        conditions_tmp = []
        for s, out in cond_str_dict.items():
            conditions_tmp.append((out, eval(s, {}, {})))

        def custom_decision_tree(evt):
            e = evt
            for token in conditions_tmp:
                task_id_out, lambda_condition = token
                if lambda_condition(evt):
                    e.set_target(task_id_out)
                    break
            return e

        return custom_decision_tree

    for name, condition_list in conditional_task_list.items():

        # create the individual tasks
        counter = 0
        condition_dict = {}  # [condition_str] = target_task.
        for cond_task_tokens in condition_list:
            c_name, condition_str, func, pass_id = cond_task_tokens

            new_name = f"{c_name}:{counter}"
            hsh_func = hashlib.sha256()
            hsh_func.update(new_name.encode("utf-8"))
            task_identifier = StarTask(hsh_func.digest(), pass_id)
            task_identifier.set_nice_name(new_name)
            task_identifier.set_callable(func)
            counter += 1

            task_list.add(task_identifier)
            condition_dict[condition_str] = task_identifier

        # create master task
        func = build_master_func(condition_dict)
        hsh_func = hashlib.sha256()
        hsh_func.update(name.encode("utf-8"))
        task_identifier = StarTask(hsh_func.digest())
        task_identifier.set_nice_name(name)
        task_identifier.set_callable(func)
        task_list.add(task_identifier)

    for task in task_list:
        logger.info(f"Registered: {task}")

    program = Program(task_list=task_list, start_event=start_event)
    # program.show_dependencies()
    return program
