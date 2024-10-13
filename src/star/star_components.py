# Register tasks (hash: name, condition)

import datetime
import functools
import time
from typing import Any, Optional, Callable
from typing_extensions import Self
import dill  # typing: ignore
import uuid

# Currently global for program.
task_list: dict["TaskIdentifier", tuple[Callable, bool]] = {}

IS_ENGINE = False
BINDINGS: dict[str, Callable] = {}


class TaskIdentifier:
    """Struct representing unique task with name and condition function"""

    def __init__(
        self, task_name: str, condition_func: Optional[Callable] = None
    ) -> None:
        """Create task identifier given name and condition function

        Args:
            task_name (str): Name of task. Name used in .set_target()
            condition_func (Callable, optional): Condition function for task. Defaults to None.
        """
        self.hash = hash((task_name, condition_func))
        self.name = task_name
        self.condition = condition_func

    def __hash__(self):
        """Compute hash equivalent of task.

        Returns:
            int: hash(self)
        """
        return self.hash

    def __eq__(self, other: object) -> bool:
        """Compare if some task refers to this one.

        Args:
            other (object): TaskIdentifier object to compare to.

        Returns:
            bool: True if refer to same task.
        """
        if not (isinstance(other, TaskIdentifier)):
            return False
        return (
            self.hash == other.hash
            and self.name == other.name
            and self.condition
            == other.condition  # Not perfect. This can be None == None
        )


class Event:
    """Event Struct"""

    def __init__(self, a=0, b=0):
        """Hold values that get passed from one task to another

        Args:
            a (Any, optional): A value. Defaults to 0.
            b (Any, optional): B value. Defaults to 0.
        """
        self.a = a
        self.b = b
        self.total = None
        self.system = None

    def clear_system(self) -> None:
        """Clear out system parameters"""
        self.system = None

    def define_system(self) -> None:
        """Set system parameters to empty dictionary"""
        self.system = {}

    def set_target(self, target: str) -> None:
        """Set target task of event.

        Args:
            target (str): Label for task.
        """
        self.target = target  # for routing


class AwaitGroup:
    """Group of AwaitEvent()"""

    def __init__(
        self,
        *,
        originating_task: TaskIdentifier,
        return_event: Optional[Event] = None,
        flood_time_delay=0.001,  # 1 msec
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
        time.sleep(self.flood_time_delay)
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
        originating_task: TaskIdentifier,
    ):
        """Create Awaitable Event. Immediately sends out on creation.

        Args:
            evt (Event): Event
            originating_task (TaskIdentifier): origin TaskID
        """
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
            evt
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


def dispatch_event(evt: Event) -> None:
    """Send out event. Does not allow for checking completion. Use AwaitEvent for that.

    Args:
        evt (Event): Event to send

    Returns:
        _type_: _description_
    """
    if not (IS_ENGINE):
        return None

    # recv_event(evt)  # equiv.

    f = BINDINGS["dispatch_event"]
    return f(evt)


class Task:
    """A Task Struct"""

    def __init__(self, task_id: TaskIdentifier, func):
        self.task_id = task_id
        self.func = func
        self.name = task_id.name


class Program:
    """A program struct"""

    def __init__(
        self,
        *,
        task_list: Optional[dict[TaskIdentifier, tuple[Callable, bool]]] = None,
        read_pgrm: Optional[str] = None,
        start_event: Optional[Event] = None,
    ):
        """Create Program Object

        Args:
            task_list (Optional[dict[TaskIdentifier, tuple[Callable, bool]]], optional): Task list. Generated from decorator. Defaults to None.
            read_pgrm (Optional[str], optional): String of binary program package. Defaults to None.
            start_event (Optional[Event], optional): Initial Event When Program Loaded. Defaults to None.
        """
        self.task_list = task_list
        self.saved_data: dict[str, Any] = {}
        if read_pgrm is not None:
            self.read_program(read_pgrm)

        self.start = None
        if start_event is not None:
            self.start = start_event

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
            dill.dump(save_data, f, fmode=dill.CONTENTS_FMODE)

    def read_program(self, fname: str):
        """Read program from binary program package

        Args:
            fname (str): Filename of binary program package
        """
        with open(fname, "rb") as f:
            dat = dill.load(f)
            # print(f"Opened program compiled on {dat['date_compiled']}")
            self.task_list = dat["task_list"]
            self.saved_data = dat


############################################################


def task(name: str, condition: Optional[Callable] = None, pass_task_id=False):
    """Decorator for building a task

    Args:
        name (str): Name of task. Can use in star.Event().set_target()
        condition (Optional[Callable], optional): Function that returns bool to select task. Defaults to None (no condition)
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
        task_condition = TaskIdentifier(name, condition)

        task_list[task_condition] = (f_wrap, pass_task_id)
        print(
            f"Registered task {name} with condition {condition} with ID: {hash(task_condition)}"
        )

        return f_wrap

    return wrap


def compile(start_event: Event) -> Program:
    """Compile star program into binary package for import into engine

    Args:
        start_event (Event): Event to fire when program loaded

    Returns:
        Program: Program Object
    """
    program = Program(task_list=task_list, start_event=start_event)
    # program.show_dependencies()
    return program
