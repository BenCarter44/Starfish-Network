import concurrent
import concurrent.futures
import functools
from threading import Thread
import threading
from typing import Any, Callable, cast
import uuid
import star_components as star
import asyncio
import time

DEBUG = True


def debug_print(a):
    """Print a if DEBUG is True

    Args:
        a (any): Print Me
    """
    if not (DEBUG):
        return
    print(a)


class ProgramExecutor:
    """Struct representing imported program"""

    def __init__(self, start_target: star.Event):
        self.start_target = start_target


class NodeEngine:
    def __init__(self):
        """Create Node with compute workers and engine units."""
        self.total_engine_units = 1000
        self.count_host = 0

        self.hosted_tasks: dict[
            star.TaskIdentifier,
            dict[str, tuple[Callable, bool] | asyncio.Semaphore | star.TaskIdentifier],
        ] = {
            "test": {"task": (print, False), "count": asyncio.Semaphore(20)}  # type: ignore
        }
        self.hosted_tasks = {}
        self.hosted_tasks_names: dict[str, list[star.TaskIdentifier]] = {}

        self.out_unified_queue: asyncio.Queue[star.Event] = asyncio.Queue()
        self.executor_queue: asyncio.Queue[Any] = asyncio.Queue()

        self.node_id = uuid.uuid4()
        self.await_triggers: dict[
            tuple[uuid.UUID, star.TaskIdentifier],
            dict[str, threading.Event | star.Event | None],
        ] = {}

        # asyncio loop
        self.async_loop = asyncio.new_event_loop()
        self.async_tasks = set()
        self.run_thread = self.run()
        while len(self.async_tasks) < 2:
            time.sleep(0.01)
            pass  # wait for the two async tasks to start

    def import_program(self, pgrm: star.Program) -> ProgramExecutor:
        """Import program into engine.

        Args:
            pgrm (star.Program): Program to import

        Raises:
            ValueError: If program has no tasks, raise ValueError

        Returns:
            ProgramExecutor: Program Executor Object
        """
        task_list = pgrm.task_list
        if task_list is None:
            raise ValueError("No Tasks!")

        self.count_host += len(task_list)

        for task_id, func_pair in task_list.items():
            m = (self.total_engine_units // self.count_host) + 1
            debug_print(f"I: {hash(task_id)}: {func_pair} - Count: {m}")
            self.hosted_tasks[task_id] = {
                "task": func_pair,
                "count": asyncio.Semaphore(m),
                "task_id": task_id,
            }

            if task_id.name not in self.hosted_tasks_names:
                self.hosted_tasks_names[task_id.name] = [task_id]
            else:
                self.hosted_tasks_names[task_id.name].append(task_id)

        return ProgramExecutor(pgrm.saved_data["start"])

    def start_program(self, pgrm_exc: ProgramExecutor, local=False):
        """Start program in engine by firing the start event from program.

        Args:
            pgrm_exc (ProgramExecutor): Program to start.
            local (bool, optional): Not Implemented. For keeping a program from migrating off engine. Defaults to False.
        """
        # if local is True, keep tasks on this machine only (like console)
        # if local is False, distribute tasks across network.

        debug_print("D: Start pgrm")
        start_event = pgrm_exc.start_target
        self.recv_event(start_event)

    ########################## Engine.

    async def recv_event_coro(self, evt: star.Event):
        """ASYNC COROUTINE. Consume a receiving event.

        Args:
            evt (star.Event): Receiving event.
        """
        debug_print(f"I: Recv: {evt.target}")
        # debug_print("I: Recv Sys: ", evt.system)
        if (
            evt.system is not None
            and evt.system["await"]
            and not (evt.system["initial"])
        ):
            debug_print("I: Received sys callback")
            await self.await_recv(evt)
            return

        # check to see if event is in the current task list
        if evt.target not in self.hosted_tasks_names:
            debug_print(
                f"I: Received event: {evt.target}. Target not in hosted tasks. Send to network"
            )
            await self.out_unified_queue.put(evt)
            return

        # get all tasks with the specific name
        tasks: list[star.TaskIdentifier] = self.hosted_tasks_names[evt.target]
        # find the one that matches the condition.
        correct = None
        for t in tasks:
            if t.condition is None:
                correct = t
                break
            check = t.condition(evt)
            if check:
                correct = t
                break

        if correct is None:
            debug_print(
                f"I: Received event: {evt.target}. Target condition not in hosted tasks. Send to network"
            )
            await self.out_unified_queue.put(evt)
            return

        # is currently being hosted.
        host_information = self.hosted_tasks[cast(star.TaskIdentifier, correct)]

        if cast(asyncio.Semaphore, host_information["count"]).locked():
            # no resources left!
            debug_print(
                f"I: Received event: {evt.target}. No compute units left! Send to network"
            )
            await self.out_unified_queue.put(evt)
            return

        debug_print(f"I: Received event: {evt.target}. Waiting....")
        await cast(
            asyncio.Semaphore, host_information["count"]
        ).acquire()  # acquire sem
        debug_print(f"I: Done Waiting.... Put in Execution Queue")
        await self.executor_queue.put((host_information, evt))
        return

    def recv_event(self, evt: star.Event):
        """OUTSIDE API. Consume a receiving event.

        Args:
            evt (star.Event): Receiving event.
        """
        assert isinstance(evt, star.Event)
        f = asyncio.run_coroutine_threadsafe(self.recv_event_coro(evt), self.async_loop)

    async def executor_loop(self):
        """ASYNC TASK. Handle the executor queue and pool"""
        with concurrent.futures.ThreadPoolExecutor() as pool:
            while True:
                item = await self.executor_queue.get()
                func, requires_task_id = item[0]["task"]
                sem = item[0]["count"]
                task_id = item[0]["task_id"]
                evt = item[1]

                debug_print(
                    f"I: EX Queue: {evt.target}. Remaining tast compute units: {sem._value}. Total Across All Tasks Queue: {pool._work_queue.qsize()}. Total Workers Alloc: {len(pool._threads)} Total Workers: {pool._max_workers}."
                )

                if not (requires_task_id):
                    out_future = self.async_loop.run_in_executor(
                        pool, functools.partial(func, evt)
                    )
                else:
                    out_future = self.async_loop.run_in_executor(
                        pool, functools.partial(func, evt, task_id)
                    )

                out_future.add_done_callback(functools.partial(self.finish_task, sem))
                # await send_to_out_queue(out)

    def finish_task(
        self,
        sem: asyncio.Semaphore,
        evt_future: concurrent.futures.Future[star.Event],
    ):
        """Callback. Send out event generated from task.

        Args:
            evt (star.Event): Receiving event.
        """
        evt = evt_future.result()

        if evt.system is not None and evt.system["await"] and evt.system["initial"]:
            evt.system["initial"] = False

        sem.release()
        debug_print(
            f"I: EX Done. Send Target: {evt.target}. Now, remaining compute units: {sem._value}."
        )
        self.recv_event(evt)

    async def output_loop(self):
        """ASYNC TASK. Send output events."""
        while True:
            item = await self.out_unified_queue.get()
            debug_print("I: SENDING: ", item)

    async def debug_loop(self):
        """ASYNC TASK. Is Alive Debug Loop"""
        while True:
            print(".")
            await asyncio.sleep(1)

    async def await_recv(self, evt: star.Event) -> None:
        """ASYNC COROUTINE. Handle system await events generated by AwaitEvent()

        Args:
            evt (star.Event): event returned by subject of await event call.
        """
        if evt.system["node"] != self.node_id or not (evt.system["await"]):
            return  # Drop. Does not refer to me!

        # look up trigger in table. If not False, ignore
        if evt.system["trigger"] not in self.await_triggers:
            return  # Drop. Trigger not found.

        # see if event is for matching function!
        if evt.target != evt.system["previous"].target:
            debug_print("I: Drop Await return. Event is for different target")
            return  # Drop. Event is for different target.

        trigger = evt.system["trigger"]
        if cast(threading.Event, self.await_triggers[trigger]["alert"]).is_set():
            return  # Already triggered! Drop!

        evt.clear_system()

        self.await_triggers[trigger]["data"] = evt
        cast(
            threading.Event, self.await_triggers[trigger]["alert"]
        ).set()  # alert that you're done!

    def await_trigger(
        self, trigger: tuple[uuid.UUID, star.TaskIdentifier], timeout=2.0
    ) -> star.Event:
        """Wait for await_event trigger. Used by AwaitEvent

        Args:
            trigger (tuple[uuid.UUID, star.TaskIdentifier]): Trigger ID
            timeout (float, optional): Timeout for waiting. Defaults to 2.0.

        Raises:
            TimeoutError: Past timeout

        Returns:
            star.Event: event.
        """
        debug_print(
            f"D: Trigger created: {cast(threading.Event, self.await_triggers[trigger]['alert']).is_set()}"
        )
        i = cast(threading.Event, self.await_triggers[trigger]["alert"]).wait(
            timeout=timeout
        )
        if i:
            return cast(star.Event, self.await_triggers[trigger]["data"])
        else:
            raise TimeoutError

    def await_trigger_check(
        self,
        trigger: tuple[uuid.UUID, star.TaskIdentifier],
    ) -> bool:
        """Check if trigger has been received.

        Args:
            trigger (tuple[uuid.UUID, star.TaskIdentifier]): Trigger ID

        Returns:
            bool: Trigger received.
        """
        # TODO: Create struct for triggers.
        return cast(threading.Event, self.await_triggers[trigger]["alert"]).is_set()

    def create_trigger(
        self, task_id: star.TaskIdentifier
    ) -> tuple[uuid.UUID, star.TaskIdentifier]:
        """Create trigger for TaskID.

        Args:
            task_id (star.TaskIdentifier): TaskID

        Returns:
            tuple[uuid.UUID, star.TaskIdentifier]: TriggerID
        """
        original_task_id = task_id
        trigger_id = (uuid.uuid4(), original_task_id)

        self.await_triggers[trigger_id] = {
            "alert": threading.Event(),
            "data": None,
        }
        cast(threading.Event, self.await_triggers[trigger_id]["alert"]).clear()

        return trigger_id

    def clean_trigger(self, trigger: tuple[uuid.UUID, star.TaskIdentifier]):
        """Remove trigger from engine

        Args:
            trigger (tuple[uuid.UUID, star.TaskIdentifier]): TriggerID
        """
        del self.await_triggers[trigger]

    async def start_loops(self):
        """ASYNC COROUTINE. Start the various ASYNC Tasks"""
        debug_print("D: Start Loops")
        executor_loop_t = asyncio.create_task(
            self.executor_loop(), loop=self.async_loop
        )
        output_loop_t = asyncio.create_task(self.output_loop(), loop=self.async_loop)
        # debug_loop_t = asyncio.create_task(self.debug_loop())
        self.async_tasks.add(executor_loop_t)
        self.async_tasks.add(output_loop_t)
        # self.async_tasks.add(debug_loop_t)

    def _run_thread(self):
        """Run the asyncio event loop here."""
        debug_print("D: Running")
        asyncio.set_event_loop(self.async_loop)
        self.async_loop.set_debug(True)
        self.async_loop.run_forever()

    def run(self) -> Thread:
        """Create the running thread and start it.

        Returns:
            Thread: Event loop thread.
        """
        self.async_engine = Thread(target=self._run_thread)
        self.async_engine.start()
        asyncio.run_coroutine_threadsafe(self.start_loops(), self.async_loop)
        return self.async_engine

    def return_component_bindings(self) -> dict:
        """Return function bindings for star.components

        Returns:
            dict: BINDINGS
        """
        out = {
            "dispatch_event": self.recv_event,
            "get_node_id": lambda: self.node_id,
            "await_trigger": self.await_trigger,
            "create_trigger": self.create_trigger,
            "is_trigger_ready": self.await_trigger_check,
            "cleanup_trigger": self.clean_trigger,
        }
        return out


############################### LOAD PROGRAM


pgrm = star.Program(read_pgrm="my_program.star")
print(
    f"I: Opening program '{pgrm.saved_data['pgrm_name']}' from {pgrm.saved_data['date_compiled']}\n"
)

compute_node = Node()
star.IS_ENGINE = True
star.BINDINGS = compute_node.return_component_bindings()
exc = compute_node.import_program(pgrm)
compute_node.start_program(exc, local=True)

compute_node.run_thread.join()
