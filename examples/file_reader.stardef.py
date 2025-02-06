import sys
import time
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))
try:
    from ..src.core import star_components as star
    from ..src.core import File
except:
    from core import star_components as star
    from core import File

import logging

logger = logging.getLogger(__name__)


@star.task("start_program", pass_task_id=True)
def start_program(evt: star.Event, task: star.StarTask):
    file_factory = task.get_file_factory()
    file = file_factory.File(task.get_user(), "/test")
    file.create()
    file.open()
    file.write(b"0")
    file.close()

    evt_new = star.Event()
    evt_new.set_target("read_file")
    return evt_new


@star.task("read_file", pass_task_id=True)
def read_file(evt: star.Event, task: star.StarTask):
    import time
    import os

    file_factory = task.get_file_factory()
    file = file_factory.File(task.get_user(), "/test")
    file.open()
    number = int(file.read().decode("utf-8"))
    file.seek(0, os.SEEK_SET)
    file.write(str(number + 1).encode("utf-8"))
    file.close()

    # f = open("example.txt", "w+")

    evt_new = star.Event()
    # evt_new.data["count"] = evt.data["count"] + 1
    # counter = evt.data["count"]

    # file.write(str(counter).encode("utf-8"))
    # file.write(b"\n")
    # file.close()

    time.sleep(5)

    evt_new.set_target("read_file")

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
    start_event.data["count"] = 0
    start_event.set_target("start_program")
    pgrm = star.compile(start_event=start_event)
    pgrm.save("file_program.star")
