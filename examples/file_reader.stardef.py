import sys
import time
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))
try:
    from ..src.core import star_components as star
except:
    from core import star_components as star

import logging

logger = logging.getLogger(__name__)


@star.task("read_file", pass_task_id=True)
def read_file(evt: star.Event, task: star.StarTask):
    import time

    f = open("example.txt", "w+")

    evt_new = star.Event()
    evt_new.data["count"] = evt.data["count"]
    evt_new.set_target("counter_add")
    aw = star.AwaitEvent(evt_new, task)
    evt_ret = aw.wait_for_result()
    counter = evt_ret.data["count"]

    f.write(str(counter))
    f.write("\n")
    f.close()

    time.sleep(1)

    evt_out = star.Event()
    evt_out.set_target("read_file")
    evt_out.data["count"] = counter

    return evt_out


@star.task("counter_add")
def counter(evt):
    evt.data["count"] = evt.data["count"] + 1
    return evt


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
    start_event.data["count"] = 0
    start_event.set_target("read_file")
    pgrm = star.compile(start_event=start_event)
    pgrm.save("file_program.star")
