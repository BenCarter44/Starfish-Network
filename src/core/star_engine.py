import concurrent
import concurrent.futures
import functools
import random
from threading import Thread
import threading
from typing import Any, Callable, Optional, cast
import uuid
import src.core.star_components as star
import asyncio
import time
import logging

import os, sys

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

logger = logging.getLogger(__name__)

DEBUG = True


class ProgramExecutor:
    """Struct representing imported program"""

    def __init__(self, start_target: star.Event):
        self.start_target = start_target


class NodeEngine:
    def __init__(self, node_id):
        """Create Node with compute workers and engine units."""
        self.total_engine_units = 1000
        self.count_host = 0

        self.hosted_tasks: dict[
            star.StarTask, tuple[star.StarTask, asyncio.Semaphore]
        ] = {}

        self.out_unified_queue: asyncio.Queue[star.Event] = asyncio.Queue()
        self.executor_queue: asyncio.Queue[tuple[star.StarTask, star.Event]] = (
            asyncio.Queue()
        )

        self.node_id = node_id
        self.await_triggers: dict[
            tuple[uuid.UUID, star.StarTask],
            dict[str, threading.Event | star.Event | None],
        ] = {}

        star.IS_ENGINE = True

        # asyncio loop
        self.async_tasks = set()
        self.send_event_handler = lambda evt: evt  # replaced by Node.
        self.loop = asyncio.get_event_loop()
        self.plugboard_internal = None
        star.BINDINGS = self.return_component_bindings()
        # self.task_to_process: dict[bytes, star.StarProcess] = {}

    def import_task(self, task: star.StarTask, process: star.StarProcess):
        """Import task into engine.

        Args:
            task: (star.StarTask) Task to allocate

        """
        logger.debug(f"ENGINE - ENGINE - Engine import! {task.get_id()}")
        if task in self.hosted_tasks:
            return

        self.count_host += 1
        self.hosted_tasks[task] = (task, asyncio.Semaphore(1000))
        # self.task_to_process[task.get_id()] = process

    def start_program(self, pgrm_exc: ProgramExecutor, local=False):
        """Start program in engine by firing the start event from program.

        Args:
            pgrm_exc (ProgramExecutor): Program to start.
            local (bool, optional): Not Implemented. For keeping a program from migrating off engine. Defaults to False.
        """
        # if local is True, keep tasks on this machine only (like console)
        # if local is False, distribute tasks across network.

        logger.debug(f"ENGINE - Start pgrm")
        start_event = pgrm_exc.start_target
        self.recv_event(start_event)

    ########################## Engine.

    async def recv_event_coro(self, evt: star.Event) -> int:
        """ASYNC COROUTINE. Consume a receiving event. Send event to the task.

        Args:
            evt (star.Event): Receiving event.

        Returns:
            (int): number of compute units for that task remaining.
        """

        # go here. Now, the event will have an empty user and process bytes. (if from engine)
        # if from network, it will have filled out user and process bytes

        if (
            evt.system is not None
            and evt.system["await"]
            and not (evt.system["initial"])
        ):
            logger.error(
                "ENGINE - Received sys callback. Dropping. Await events not supported!"
            )
            # await self.await_recv(evt)
            return -1

        incoming_target = evt.target

        if incoming_target not in self.hosted_tasks:
            logger.warning("ENGINE - Passed in task ID but not hosting. Forwarding")
            await self.out_unified_queue.put(evt)
            return -2

        if self.hosted_tasks[incoming_target][1].locked():
            # no resources left!
            logger.info(
                f"ENGINE - Received event: {evt.target}. {self.node_id} No compute units left! Send to network"
            )
            await self.out_unified_queue.put(evt)
            return 0

        a = None
        if evt.origin is not None:
            a = evt.origin.target.get_id().hex()
        logger.info(
            f"ENGINE - Received event: {evt.target}. Org: {a} {self.node_id.hex()} Waiting...."
        )
        await self.hosted_tasks[incoming_target][1].acquire()  # acquire sem
        logger.info(f"ENGINE - Done Waiting.... Put in Execution Queue")

        evt.target.monitor = self.hosted_tasks[incoming_target][0].monitor

        exc_task = self.hosted_tasks[incoming_target][0]
        await self.executor_queue.put((exc_task, evt))
        return self.hosted_tasks[incoming_target][1]._value

    def update_monitor(self, task: star.StarTask, monitor: bytes):
        if task not in self.hosted_tasks:
            logger.info(f"ENGINE - Not found {task.get_id()} monitor")
            return
        self.hosted_tasks[task][0].monitor = monitor

    def recv_event(self, evt: star.Event, increment=False):
        """OUTSIDE API. Consume a receiving event.

        Args:
            evt (star.Event): Receiving event.
        """
        assert isinstance(evt, star.Event)

        if increment:
            evt.nonce += 1

        if evt.target not in self.hosted_tasks:
            logger.warning("ENGINE - Passed in task ID but not hosting. Forwarding")

            async def tmp():
                await self.out_unified_queue.put(evt)

            asyncio.run_coroutine_threadsafe(tmp(), self.loop)
            return -3

        f = asyncio.run_coroutine_threadsafe(self.recv_event_coro(evt), self.loop)
        v = self.hosted_tasks[evt.target][1]._value - 1
        if v < 0:
            return 0
        else:
            return v

    async def executor_loop(self):
        """ASYNC TASK. Handle the executor queue and pool"""
        logger.debug(f"ENGINE - Executor Loop Running")
        with concurrent.futures.ThreadPoolExecutor() as pool:
            while True:
                task, evt = await self.executor_queue.get()  # get the task
                if evt.origin is None or evt.is_checkpoint:
                    evt_copy = evt.to_bytes()  # old event (set to current)
                else:
                    evt_copy = evt.origin.to_bytes()  # keep the same old event.

                if evt.origin_previous is None or evt.is_checkpoint:
                    if evt.origin is None:
                        evt_copy_pre = evt_copy  # old event (set to current)
                    else:
                        evt_copy_pre = evt.origin.to_bytes()
                else:
                    evt_copy_pre = (
                        evt.origin_previous.to_bytes()
                    )  # keep the same old event.

                # for file factory
                task.plugboard_callback = self.plugboard_internal
                task.node_callback = self.plugboard_internal.node_object
                task.loop_callback = self.loop
                task.hold_past_event = evt
                task.hold_past_event_pre = star.StarTask.from_bytes(evt_copy_pre)
                func = task.get_callable()
                if func is None:
                    logger.error("ENGINE - Function is NONE! skipping.")
                    continue

                logger.info(
                    f"ENGINE - EX Queue: {task}. Total Workers Alloc: {len(pool._threads)} Total Workers: {pool._max_workers}."
                )
                a = None
                if evt.origin is not None:
                    a = evt.origin.target.get_id()

                logger.info(f"ENGINE - Run: {task} Org: {a}")
                logger.debug(f"ENGINE - {func}")

                if not (task.pass_id):
                    out_future = asyncio.get_event_loop().run_in_executor(
                        pool, functools.partial(func, evt)
                    )
                else:
                    out_future = asyncio.get_event_loop().run_in_executor(
                        pool, functools.partial(func, evt, task)
                    )

                out_future.add_done_callback(
                    functools.partial(
                        self.finish_task,
                        task,
                        star.Event.from_bytes(evt_copy),
                        star.Event.from_bytes(evt_copy_pre),
                    )
                )
                # await send_to_out_queue(out)

    def finish_task(
        self,
        task: star.StarTask,
        old_event: star.Event,
        old_event_pre: star.Event,
        evt_future: concurrent.futures.Future[star.Event],
    ):
        """Callback. Send out event generated from task.

        Args:
            evt (star.Event): Receiving event.
        """
        evt = evt_future.result()
        if evt is None:
            logger.warning("ENGINE - Malformed event! Dropping! (or kill event)")
            return

        # if evt.is_checkpoint:  # only track if IS CHECKPOINT.
        evt.origin = old_event
        evt.origin_previous = old_event_pre
        evt.nonce = old_event.nonce
        if evt.system is not None and evt.system["await"] and evt.system["initial"]:
            evt.system["initial"] = False

        if evt.target is None:
            logger.info("ENGINE - Process thread finished")
            return

        # clear out the user/proc id and replace it with the task.
        evt.target.attach_to_process_task(task)

        logger.info(
            f"ENGINE - EX Done. Send Target: {evt.target}. Origin: {old_event.target} Origin-Pre: {old_event_pre.target}. Monitor: {old_event.target.monitor}. Monitor-pre: {old_event_pre.target.monitor}"
        )

        # assume the condition is none. It will already have condition or not
        async def send_quick(evt):
            await self.out_unified_queue.put(evt)

        asyncio.run_coroutine_threadsafe(send_quick(evt), loop=self.loop)

    async def output_loop(self):
        """ASYNC TASK. Send output events."""
        while True:
            item: star.Event = await self.out_unified_queue.get()
            logger.debug(f"ENGINE - SENDING: {item}")

            # if item.target.get_id() not in self.task_to_process:
            #     logger.error(
            #         "Attempted to send task from engine that is not a currently running process!"
            #     )
            #     return
            # await self.send_event_handler(item)
            try:
                await self.send_event_handler(item)
                pass
            except Exception as e:
                logger.critical(e)
                sys.exit(2)

    async def debug_loop(self):
        """ASYNC TASK. Is Alive Debug Loop"""
        while True:
            print(".")
            await self.async_loop.sleep(1)

    # async def await_recv(self, evt: star.Event) -> None:
    #     """ASYNC COROUTINE. Handle system await events generated by AwaitEvent()

    #     Args:
    #         evt (star.Event): event returned by subject of await event call.
    #     """
    #     if evt.system["node"] != self.node_id or not (evt.system["await"]):
    #         # print(evt.system)
    #         # print(self.node_id)
    #         logger.warning("System node mismatch")
    #         return  # Drop. Does not refer to me!

    #     # look up trigger in table. If not False, ignore
    #     if evt.system["trigger"] not in self.await_triggers:
    #         logger.warning("Trigger unknown")
    #         return  # Drop. Trigger not found.

    #     # see if event is for matching function!
    #     if evt.target != evt.system["previous"].target:
    #         logger.warning("Drop Await return. Event is for different target")
    #         return  # Drop. Event is for different target.

    #     trigger = evt.system["trigger"]
    #     if cast(threading.Event, self.await_triggers[trigger]["alert"]).is_set():
    #         logger.warning("Already triggered! Drop!")
    #         return  # Already triggered! Drop!

    #     evt.clear_system()

    #     self.await_triggers[trigger]["data"] = evt
    #     logger.info(f"GOT: {evt.data}")
    #     cast(
    #         threading.Event, self.await_triggers[trigger]["alert"]
    #     ).set()  # alert that you're done!

    # def await_trigger(
    #     self, trigger: tuple[uuid.UUID, star.StarTask], timeout=2.0
    # ) -> star.Event:
    #     """Wait for await_event trigger. Used by AwaitEvent

    #     Args:
    #         trigger (tuple[uuid.UUID, star.StarTask]): Trigger ID
    #         timeout (float, optional): Timeout for waiting. Defaults to 2.0.

    #     Raises:
    #         TimeoutError: Past timeout

    #     Returns:
    #         star.Event: event.
    #     """
    #     logger.info(
    #         f"Trigger created: {cast(threading.Event, self.await_triggers[trigger]['alert']).is_set()}"
    #     )
    #     i = cast(threading.Event, self.await_triggers[trigger]["alert"]).wait(
    #         timeout=timeout
    #     )
    #     if i:
    #         return cast(star.Event, self.await_triggers[trigger]["data"])
    #     else:
    #         raise TimeoutError

    # def await_trigger_check(
    #     self,
    #     trigger: tuple[uuid.UUID, star.StarTask],
    # ) -> bool:
    #     """Check if trigger has been received.

    #     Args:
    #         trigger (tuple[uuid.UUID, star.StarTask]): Trigger ID

    #     Returns:
    #         bool: Trigger received.
    #     """
    #     # TODO: Create struct for triggers.
    #     return cast(threading.Event, self.await_triggers[trigger]["alert"]).is_set()

    # def create_trigger(self, task_id: star.StarTask) -> tuple[uuid.UUID, star.StarTask]:
    #     """Create trigger for TaskID.

    #     Args:
    #         task_id (star.StarTask): TaskID

    #     Returns:
    #         tuple[uuid.UUID, star.StarTask]: TriggerID
    #     """
    #     original_task_id = task_id
    #     trigger_id = (uuid.uuid4(), original_task_id.get_id())

    #     self.await_triggers[trigger_id] = {
    #         "alert": threading.Event(),
    #         "data": None,
    #     }
    #     cast(threading.Event, self.await_triggers[trigger_id]["alert"]).clear()

    #     return trigger_id

    # def clean_trigger(self, trigger: tuple[uuid.UUID, star.StarTask]):
    #     """Remove trigger from engine

    #     Args:
    #         trigger (tuple[uuid.UUID, star.StarTask]): TriggerID
    #     """
    #     del self.await_triggers[trigger]

    async def start_loops(self):
        """ASYNC COROUTINE. Start the various ASYNC Tasks"""
        logger.info("ENGINE - Start Loops")
        executor_loop_t = asyncio.create_task(self.executor_loop())
        output_loop_t = asyncio.create_task(self.output_loop())
        # debug_loop_t = asyncio.create_task(self.debug_loop())
        self.async_tasks.add(executor_loop_t)
        self.async_tasks.add(output_loop_t)
        # self.async_tasks.add(debug_loop_t)

    # def _run_thread(self):
    #     """Run the asyncio event loop here."""
    #     logger.info("Running")
    #     # asyncio.set_event_loop(self.async_loop)
    #     self.async_loop.set_debug(True)
    #     self.async_loop.run_forever()

    def return_component_bindings(self) -> dict:
        """Return function bindings for star.components

        Returns:
            dict: BINDINGS
        """
        out = {
            "dispatch_event": self.recv_event,
            "get_node_id": lambda: self.node_id,
            # "await_trigger": self.await_trigger,
            # "create_trigger": self.create_trigger,
            # "is_trigger_ready": self.await_trigger_check,
            # "cleanup_trigger": self.clean_trigger,
        }
        return out


############################### LOAD PROGRAM

if __name__ == "__main__":
    pgrm = star.Program(read_pgrm="my_program.star")
    print(
        f"Opening program '{pgrm.saved_data['pgrm_name']}' from {pgrm.saved_data['date_compiled']}\n"
    )

    # compute_node = NodeEngine()
    # star.IS_ENGINE = True
    # star.BINDINGS = compute_node.return_component_bindings()
    # exc = compute_node.import_program(pgrm)
    # compute_node.start_program(exc, local=True)

    # compute_node.run_thread.join()
