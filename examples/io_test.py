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
    import time

    io_factory = task.get_io_factory()
    IO_NONEXIST, IO_BUSY, IO_DETACHED, IO_OK = io_factory.get_io_constants()
    dev = io_factory.IODevice(b"\x00\x22\x00\x05\x04\x03\x02\x01", "/dev/tty0")

    status = dev.open()
    if status != IO_OK:
        print("Unable to open device!")
        if status == IO_NONEXIST:
            print("Device nonexist!")
        if status == IO_BUSY:
            print("Device busy by another process")
        if status == IO_DETACHED:
            print("Device detached")
        print("STOP")
        time.sleep(1000)

    dev.write(b"\r\nWelcome to the program!\r\n")

    evt_new = star.Event()
    evt_new.data["io_dev"] = dev.export()
    evt_new.set_target("read_file")
    return evt_new


@star.task("read_file", pass_task_id=True)
def read_file(evt: star.Event, task: star.StarTask):
    import time
    import os

    io_factory = task.get_io_factory()
    IO_NONEXIST, IO_BUSY, IO_DETACHED, IO_OK = io_factory.get_io_constants()
    dev = io_factory.IODevice_Import(evt.data["io_dev"])

    counter = 0
    while True:
        available, status = dev.read_available()
        if status != IO_OK:
            break
        if available:
            r, status = dev.read()
            dev.write(r)
            if r == b"\r":
                dev.write(b"\n")
            counter = 0
        elif counter < 10:
            counter += 1
        else:
            time.sleep(0.1)
            counter = 0

    print("END OF PROGRAM")
    time.sleep(1000)
    # dev.write(b"Hello again!\r\n")
    # dev.write(b"Could you type your name: \r\n")

    # while True:
    #     if dev.read_available():
    #         break
    #     time.sleep(0.1)

    # name = dev.read()
    # dev.write(b"Hello {name}\r\n")

    # f = open("example.txt", "w+")

    evt_new = star.Event()
    evt_new.set_target("read_file")
    evt_new.data["io_dev"] = dev.export()

    time.sleep(1)
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
    pgrm.save("io_program.star")
