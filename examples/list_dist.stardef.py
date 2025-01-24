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

    return evt_new


@star.task("cast_numbers", checkpoint=False)
def cast_numbers(evt):
    evt_new = star.Event()
    evt_new.data["a"] = int(evt.data["a"])
    evt_new.data["b"] = int(evt.data["b"])
    evt_new.set_target("run_total")
    return evt_new


@star.task("run_total", checkpoint=False)
def run_total(evt):
    evt_new = star.Event()
    total = evt.data.get("a") + evt.data.get("b")
    evt_new.data["total"] = total
    evt_new.set_conditional_target("print_conditional")
    return evt_new


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


# Condition: None
@star.task("list_intro", pass_task_id=True)
def list_intro(evt, task_id: star.StarTask):
    i = input("Please type a string: ")
    string = i.upper()
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
