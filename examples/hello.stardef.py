import sys
import time
import os


sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))
try:
    from ..src.KernelCommands import CapturingArgumentParser
    from ..src.core import star_components as star
except:
    from core import star_components as star
    from KernelCommands import CapturingArgumentParser

import logging

logger = logging.getLogger(__name__)

# Currently for simplicity only one user on telnet at once per node.


# ======================================================================================

# Will do:
#   - ls
#   - echo
#   - echo_file <file>
#   - cat <file>
#   - run <program>
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

# =======================================================================================


@star.task("start_program", pass_task_id=True)
def start_program(evt: star.Event, task: star.StarTask):
    import time

    io_factory = task.get_io_factory()
    IO_NONEXIST, IO_BUSY, IO_DETACHED, IO_OK = io_factory.get_io_constants()

    # Check for input device argument
    result = evt.data.get("sys_shell_device")

    if result is None:
        evt_out = star.Event()
        evt_out.set_target("exit_handler")
        return evt_out

    dev = io_factory.IODevice_FromID(result)

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
        evt_out = star.Event()
        evt_out.set_target("exit_handler")
        return evt_out

    evt_out = star.Event()
    evt_out.data["device"] = dev.export()
    evt_out.set_target("main")

    return evt_out


@star.task("main", pass_task_id=True)
def main_pgrm(evt: star.Event, task: star.StarTask):
    from src.util.util import decompress_bytes_to_str
    import time

    device_raw = evt.data.get("device")
    if device_raw is None:
        evt_out = star.Event()
        evt_out.set_target("exit_handler")
        return evt_out

    print("HELLO ATTACHED TO DEVICE")
    io_factory = task.get_io_factory()
    IO_NONEXIST, IO_BUSY, IO_DETACHED, IO_OK = io_factory.get_io_constants()

    device = io_factory.IODevice_Import(device_raw)

    header = "\nHello World From My Program!\n"
    device.write(header.encode("utf-8"))
    time.sleep(2)
    evt_new = star.Event()
    evt_new.data["device"] = device.export()
    evt_new.set_target("exit_handler_device")
    return evt_new


@star.task("exit_handler")
def exit_handler(evt: star.Event):
    evt_new = star.Event()
    evt_new.set_kill_target()
    return evt_new


@star.task("exit_handler_device", pass_task_id=True)
def exit_handler_device(evt: star.Event, task: star.StarTask):
    res = evt.data.get("device")
    if res is None:
        evt_new = star.Event()
        evt_new.set_target("exit_handler")
        return evt_new

    io_factory = task.get_io_factory()
    IO_NONEXIST, IO_BUSY, IO_DETACHED, IO_OK = io_factory.get_io_constants()
    device = io_factory.IODevice_Import(res)
    result = device.close()
    evt_new = star.Event()
    evt_new.set_target("exit_handler")
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
    pgrm.save("hello.star")
