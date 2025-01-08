import time
import sys, os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))
try:
    from ..src.core import star_components as star
except:
    from core import star_components as star


import logging

logger = logging.getLogger(__name__)


@star.task("input")
def input_event(evt: star.Event):

    print("Input Event!")
    a = input("Type in a number: ")
    b = input("Type in a second number: ")

    evt_new = star.Event()
    data = {
        "a": int(a),
        "b": int(b),
    }
    evt_new.data = data
    evt_new.set_target("run_total")

    return evt_new


@star.task("run_total")
def run_total(evt):
    total = evt.data["a"] + evt.data["b"]

    evt_new = star.Event()
    data = {
        "total": total,
    }
    evt_new.data = data
    # time.sleep(2)
    evt_new.set_conditional_target("print_conditional")
    return evt_new


# Condition: total % 2 == 0
@star.conditional_task(
    "print_conditional", "lambda evt: evt.data.get('total') % 2 == 0"
)
def print_even(evt):
    total = evt.data.get("total")
    print(f"The total is even! {total}")

    evt_new = star.Event(data={"total": total})
    evt_new.set_target("input")

    return evt_new


# @star.task("print_conditional_choice", condition=None)
# def print_choice(evt):

#     e = star.Event(0, 1)
#     e.total = evt.total
#     if evt.total % 2 == 0:
#         e.set_target("print_conditional_even")

#     if evt.total % 2 == 1:
#         e.set_target("print_conditional_odd")
#     return e


# Condition: total % 2 == 1
@star.conditional_task(
    "print_conditional", "lambda evt: evt.data.get('total') % 2 == 1"
)
def print_odd(evt):
    print(f"The total is odd! {evt.data.get('total')}")

    evt_new = star.Event()
    evt_new.set_target("input")

    return evt_new


##################################################################################

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
    pgrm.save("my_program.star")
