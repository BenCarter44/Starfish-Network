import time
import os, sys

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))
try:
    from ..src.core import star_components as star
except:
    from core import star_components as star

import logging

logger = logging.getLogger(__name__)


@star.task("input", pass_task_id=True)
def input_event(evt: star.Event, task_id: star.StarTask):
    a = input("Type in a number: ")
    b = input("Type in a second number: ")

    evt_new = star.Event()
    evt_new.data = {"a": a, "b": b}
    evt_new.set_target("cast_numbers")

    # print("Await!")
    awaitable = star.AwaitEvent(evt_new, task_id)
    evt_out = awaitable.wait_for_result(timeout=30)
    # print("Done Await!")

    evt_new = star.Event()
    evt_new.data = {"a": evt_out.data["a"], "b": evt_out.data["b"]}
    evt_new.set_target("run_total")

    return evt_new


@star.task("cast_numbers")
def cast_numbers(evt):
    evt.data["a"] = int(evt.data["a"])
    evt.data["b"] = int(evt.data["b"])
    return evt


@star.task("run_total")
def run_total(evt):
    total = evt.data.get("a") + evt.data.get("b")

    # f = star_os.open("/path/to/distributed/file")
    # f.close()

    # d = star_os.open_datapipe("/path/to/data/pipe.pipe")
    # d.close()

    evt.data["total"] = total

    if evt.system is None:
        evt.set_conditional_target("print_conditional")

    # evt_new = star.Event(2, 4)
    # evt_new.total = total
    # time.sleep(5)
    # evt_new.set_target("print_conditional")

    return evt


# Condition: total % 2 == 0
@star.conditional_task(
    "print_conditional", condition="lambda evt: evt.data.get('total') % 2 == 0"
)
def print_even(evt):
    print(f"The total is even! {evt.data.get('total')}")

    evt_new = star.Event()
    evt_new.data["total"] = evt.data.get("total")
    evt_new.set_target("list_intro")

    return evt_new


# Condition: total % 2 == 1
@star.conditional_task(
    "print_conditional", condition="lambda evt: evt.data.get('total') % 2 == 1"
)
def print_odd(evt):
    print(f"The total is odd! {evt.data.get('total')}")

    evt_new = star.Event()
    evt_new.data["total"] = evt.data.get("total")
    evt_new.set_target("list_intro")

    return evt_new


@star.task("to_capital")
def to_cap(evt: star.Event):
    evt.data["token"] = evt.data.get("token").upper()
    return evt


# Condition: None
@star.task("list_intro", pass_task_id=True)
def list_intro(evt, task_id: star.StarTask):
    i = input("Please type a string: ")

    await_group = star.AwaitGroup(originating_task=task_id)
    for index, token in enumerate(i):
        # create a await event for each.
        evt = star.Event()
        evt.data["index"] = index
        evt.data["token"] = token
        evt.set_target("to_capital")
        await_group.add_event(evt)

    results = await_group.wait_result_for_all(timeout=30)
    string = list(" " * len(i))
    for result in results:
        string[result.data["index"]] = result.data["token"]

    await_group.close()

    string = "".join(string)  # type: ignore
    print(string)
    evt_new = star.Event()
    evt_new.set_target("input")
    return evt_new


if __name__ == "__main__":

    class CustomFormatter(logging.Formatter):
        grey_dark = "\x1b[38;5;7m"
        grey = "\x1b[38;5;123m"
        yellow = "\x1b[33;20m"
        red = "\x1b[31;20m"
        bold_red = "\x1b[1m\x1b[38;5;9m"
        reset = "\x1b[0m"
        format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s (%(filename)s:%(lineno)d)"  # type: ignore

        FORMATS = {
            logging.DEBUG: grey_dark + format + reset,  # type: ignore
            logging.INFO: grey + format + reset,  # type: ignore
            logging.WARNING: yellow + format + reset,  # type: ignore
            logging.ERROR: red + format + reset,  # type: ignore
            logging.CRITICAL: bold_red + format + reset,  # type: ignore
        }

        def format(self, record):  # type: ignore
            log_fmt = self.FORMATS.get(record.levelno)
            formatter = logging.Formatter(log_fmt)
            return formatter.format(record)

    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.DEBUG)
    ch.setFormatter(CustomFormatter())
    logging.basicConfig(handlers=[ch], level=logging.INFO)

    logger.info("Compiler start")

    start_event = star.Event()
    start_event.set_target("input")
    pgrm = star.compile(start_event=start_event)
    pgrm.save("my_list_program.star")
