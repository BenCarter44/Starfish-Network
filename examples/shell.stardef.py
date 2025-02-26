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

# Currently for simplicity only one user on telnet at once per node.


# Will do:
#   - ls
#   - echo
#   - echo_file <file>
#   - cat <file>
#   - ./my_program (inline with the shell)
#   - ./my_second_program (inline with the shell)
#   - disconnect (somehow tell kernel)

# Kernel commands:
#   - shell attach (start shell)
#         - this creates a file called "main_shell" which contains the device ID to connect to.
#         - then spawn the process (searches for the user's file)
#         - must disconnect first on other shell!!!
#   - ps ls
#   - ps start
#   - peer ls
#   - peer connect
#   - IO ls
#   - File ls
#   - exit (to exit to already running shell)
#   - stat
#          - general peer count, file count, io count, etc....


# Priorities???? Are there task priorities? Priorities to files?


@star.task("start_program", pass_task_id=True)
def start_program(evt: star.Event, task: star.StarTask):
    import time
    from src.util.util import decompress_bytes_to_str

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

    header = "\n\n" + "=" * 30 + "\n"
    header += "[bold]Welcome to [bright_yellow]Starfish [italic]OS[/italic][/bright_yellow] Shell[/bold]"
    dev.write(header.encode("utf-8"))

    evt_new = star.Event()
    evt_new.data["io_dev"] = dev.export()
    evt_new.data["user_nice"] = decompress_bytes_to_str(task.get_user())
    evt_new.set_target("read_file")
    return evt_new


@star.task("read_file", pass_task_id=True)
def read_file(evt: star.Event, task: star.StarTask):
    import time
    import os

    io_factory = task.get_io_factory()
    IO_NONEXIST, IO_BUSY, IO_DETACHED, IO_OK = io_factory.get_io_constants()
    dev = io_factory.IODevice_Import(evt.data["io_dev"])

    user_nice_name = evt.data["user_nice"]

    status = None
    while True:
        while True:
            available, status = dev.read_available()  # it will start with an enter
            if status != IO_OK or available:
                break
            time.sleep(0.5)

        if status != IO_OK:
            break

        r, status = dev.read()
        if r != b"\n":
            dev.write(r)
        dev.write(b"\n")

        dev.write(
            f"[green]{user_nice_name}[/green]:[turquoise2]/ $ [/turquoise2]".encode(
                "utf-8"
            )
        )

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
    evt_new.data["user_nice"] = user_nice_name

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
    pgrm.save("shell.star")
