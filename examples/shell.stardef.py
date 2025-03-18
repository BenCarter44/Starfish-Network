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
    evt_out.set_target("intro_preloop")

    return evt_out


@star.task("intro_preloop", pass_task_id=True)
def intro_preloop(evt: star.Event, task: star.StarTask):
    from src.util.util import decompress_bytes_to_str

    device_raw = evt.data.get("device")
    if device_raw is None:
        evt_out = star.Event()
        evt_out.set_target("exit_handler")
        return evt_out

    io_factory = task.get_io_factory()
    IO_NONEXIST, IO_BUSY, IO_DETACHED, IO_OK = io_factory.get_io_constants()

    device = io_factory.IODevice_Import(device_raw)

    header = "\n\n" + "=" * 30 + "\n"
    header += "[bold]Welcome to [bright_yellow]Starfish [italic]OS[/italic][/bright_yellow] Shell[/bold]\n"
    device.write(header.encode("utf-8"))

    evt_new = star.Event()
    evt_new.data["device"] = device.export()
    evt_new.data["user_nice"] = decompress_bytes_to_str(task.get_user())
    evt_new.set_target("command_loop")
    return evt_new


@star.task("command_loop", pass_task_id=True)
def command_loop(evt: star.Event, task: star.StarTask):
    import time

    device_raw = evt.data.get("device")
    if device_raw is None:
        evt_out = star.Event()
        evt_out.set_target("exit_handler")
        return evt_out

    io_factory = task.get_io_factory()
    IO_NONEXIST, IO_BUSY, IO_DETACHED, IO_OK = io_factory.get_io_constants()

    device = io_factory.IODevice_Import(device_raw)
    user_nice_name = evt.data["user_nice"]

    # Display command line
    device.write(
        f"[green]{user_nice_name}[/green]:[turquoise2]/ $ [/turquoise2]".encode("utf-8")
    )

    # wait for command.
    while True:
        available, status = device.read_available()  # per line
        if status != IO_OK:
            evt_out = star.Event()
            evt_out.data["device"] = device.export()
            evt_out.set_target("exit_handler_device")
            return evt_out
        if available:
            break
        time.sleep(0.2)

    cmd, status = device.read()
    if status != IO_OK:
        evt_out = star.Event()
        evt_out.data["device"] = device.export()
        evt_out.set_target("exit_handler_device")
        return evt_out

    evt_out = star.Event(evt.data)
    evt_out.set_target("process_command")
    evt_out.data["cmd"] = cmd.decode("utf-8")

    return evt_out


@star.task("process_command", pass_task_id=True)
def process_command(evt: star.Event, task: star.StarTask):
    import shlex
    from examples.shell_include import CommandProcessor

    res = evt.data.get("device")
    if res is None:
        evt_new = star.Event()
        evt_new.set_target("exit_handler")
        return evt_new

    io_factory = task.get_io_factory()
    IO_NONEXIST, IO_BUSY, IO_DETACHED, IO_OK = io_factory.get_io_constants()
    device = io_factory.IODevice_Import(res)

    cmd = evt.data["cmd"]

    cp = CommandProcessor(evt.data)

    items = shlex.split(cmd)
    command_input = cp.parser.parse_args(items)
    data_text = cp.parser.get_output()
    out_evt = None
    if "func" in command_input and len(data_text) < 4:
        out_evt = command_input.func(command_input)
        return out_evt

    status = device.write(data_text.encode("utf-8") + b"\n")
    if status != IO_OK:
        evt_new = star.Event()
        evt_new.set_target("exit_handler_device")
        evt_new.data["device"] = device.export()
        return evt_new

    evt_new = star.Event(evt.data)
    evt_new.set_target("command_loop")
    return evt_new


@star.conditional_task(
    "command_list", "lambda evt: evt.data.get('device_flag') is True", pass_task_id=True
)
def command_list_devices(evt: star.Event, task: star.StarTask):
    res = evt.data.get("device")
    if res is None:
        evt_new = star.Event()
        evt_new.set_target("exit_handler")
        return evt_new

    io_factory = task.get_io_factory()
    IO_NONEXIST, IO_BUSY, IO_DETACHED, IO_OK = io_factory.get_io_constants()
    device = io_factory.IODevice_Import(res)

    # all_flag = evt.data["all"]

    # list files fromm DHT

    # /path:USER   |   USER

    out = " PATH               | PEER                     \n"
    out += len(out) * "=" + "\n"
    node = task.get_node_kernel()

    device_ios = node.get_io_list()

    for dev in device_ios:
        peer = dev[1]
        name = dev[2]

        out += f" {name}:{peer.hex()[0:8]} | {peer.hex(':')}\n"

    out += "=" * 50 + "\n"

    status = device.write(out.encode("utf-8"))
    if status != IO_OK:
        evt_new = star.Event()
        evt_new.set_target("exit_handler_device")
        evt_new.data["device"] = device.export()
        return evt_new

    evt_new = star.Event(evt.data)
    evt_new.set_target("command_loop")
    return evt_new


@star.conditional_task(
    "command_list",
    "lambda evt: evt.data.get('device_flag') is not True",
    pass_task_id=True,
)
def command_list_files(evt: star.Event, task: star.StarTask):
    from src.util.util import decompress_bytes_to_str

    def sfill(s, l):
        while len(s) < l:
            s += " "
        return s

    res = evt.data.get("device")
    if res is None:
        evt_new = star.Event()
        evt_new.set_target("exit_handler")
        return evt_new

    io_factory = task.get_io_factory()
    IO_NONEXIST, IO_BUSY, IO_DETACHED, IO_OK = io_factory.get_io_constants()
    device = io_factory.IODevice_Import(res)

    all_flag = evt.data["all"]

    # list files fromm DHT

    # /path:USER   |   USER

    out = " PATH          | USER    \n"
    out += len(out) * "=" + "\n"
    node = task.get_node_kernel()

    files = node.get_file_list()

    for file in files:
        usr = file[2]
        fpath = file[3]
        if usr != decompress_bytes_to_str(task.get_user()) and not (all_flag):
            continue
        out += f" /{sfill(fpath.lower() + ':' + usr,12)} | {usr} \n"

    out += "=" * 26 + "\n"

    status = device.write(out.encode("utf-8") + b"\n")
    if status != IO_OK:
        evt_new = star.Event()
        evt_new.set_target("exit_handler_device")
        evt_new.data["device"] = device.export()
        return evt_new

    evt_new = star.Event(evt.data)
    evt_new.set_target("command_loop")
    return evt_new

    # /dev/path:PATH[0:4] | PEER_ID


@star.task("command_echo", pass_task_id=True)
def command_echo(evt: star.Event, task: star.StarTask):
    res = evt.data.get("device")
    if res is None:
        evt_new = star.Event()
        evt_new.set_target("exit_handler")
        return evt_new

    io_factory = task.get_io_factory()
    IO_NONEXIST, IO_BUSY, IO_DETACHED, IO_OK = io_factory.get_io_constants()
    device = io_factory.IODevice_Import(res)

    text = evt.data["text"]
    status = device.write(text.encode("utf-8") + b"\n")
    if status != IO_OK:
        evt_new = star.Event()
        evt_new.set_target("exit_handler_device")
        evt_new.data["device"] = device.export()
        return evt_new

    evt_new = star.Event(evt.data)
    evt_new.set_target("command_loop")
    return evt_new


@star.task("command_write", pass_task_id=True)
def command_write(evt: star.Event, task: star.StarTask):
    res = evt.data.get("device")
    if res is None:
        evt_new = star.Event()
        evt_new.set_target("exit_handler")
        return evt_new

    io_factory = task.get_io_factory()
    IO_NONEXIST, IO_BUSY, IO_DETACHED, IO_OK = io_factory.get_io_constants()
    device = io_factory.IODevice_Import(res)

    text = evt.data["text"]
    file = evt.data["file"]

    file_factory = task.get_file_factory()
    my_file = file_factory.File(task.get_user(), file)

    my_file.create(True)  # overwrite file contents
    my_file.open()
    my_file.write(text.encode("utf-8"))
    my_file.close()

    device.write(b"\n")  # ignore status of new line.

    evt_new = star.Event(evt.data)
    evt_new.set_target("command_loop")
    return evt_new


@star.task("command_cat", pass_task_id=True)
def command_cat(evt: star.Event, task: star.StarTask):
    res = evt.data.get("device")
    if res is None:
        evt_new = star.Event()
        evt_new.set_target("exit_handler")
        return evt_new

    io_factory = task.get_io_factory()
    IO_NONEXIST, IO_BUSY, IO_DETACHED, IO_OK = io_factory.get_io_constants()
    device = io_factory.IODevice_Import(res)

    file = evt.data["file"]

    file_factory = task.get_file_factory()
    my_file = file_factory.File(task.get_user(), file)

    try:
        my_file.open()
        contents = my_file.read()
        my_file.close()
    except ValueError:
        contents = b"File not found!"

    status = device.write(contents + b"\n")
    if status != IO_OK:
        evt_new = star.Event()
        evt_new.set_target("exit_handler_device")
        evt_new.data["device"] = device.export()
        return evt_new

    evt_new = star.Event(evt.data)
    evt_new.set_target("command_loop")
    return evt_new


@star.task("command_run", pass_task_id=True)
def command_run(evt: star.Event, task: star.StarTask):
    import os
    import dill
    import time

    res = evt.data.get("device")
    if res is None:
        evt_new = star.Event()
        evt_new.set_target("exit_handler")
        return evt_new

    io_factory = task.get_io_factory()
    IO_NONEXIST, IO_BUSY, IO_DETACHED, IO_OK = io_factory.get_io_constants()
    device = io_factory.IODevice_Import(res)

    pgrm = evt.data["program"]

    node = task.get_node_kernel()
    try:
        pgrm_exe = star.Program(read_pgrm=f"examples/{pgrm}")
    except:
        out = f"[red]Error reading program![/red]\n"
        device.write(out.encode("utf-8"))
        evt_new = star.Event(evt.data)
        evt_new.set_target("command_loop")
        return evt_new

    # shut down the device.
    status = device.close()
    if status != IO_OK:
        evt_new = star.Event()
        evt_new.set_target("exit_handler")
        return evt_new

    # file_factory = task.get_file_factory()
    monitor_id = os.urandom(4)
    # my_file = file_factory.File(task.get_user(), '/shlock')
    # try:
    #     my_file.open()
    # except ValueError:
    #     my_file.create()
    #     my_file.open()

    # dt = my_file.read()
    # if(len(dt) == 0):
    #     # empty!
    #     log = {device.get_id(): monitor_id}
    # else:
    #     log = dill.loads(dt)
    #     log[device.get_id()] = monitor_id

    # my_file.seek(0,os.SEEK_SET)
    # my_file.write(dill.dumps(log))
    # my_file.close()

    # pass the device to the program.
    node.start_program(
        pgrm_exe,
        task.get_user(),
        {"sys_shell_device": device.get_id(), "monitor_id": monitor_id},
    )
    time.sleep(1)
    evt_new = star.Event(evt.data)
    evt_new.set_target("wait_external")
    evt_new.data["monitor"] = monitor_id
    evt_new.data["device_id"] = device.get_id()
    return evt_new


@star.task("wait_external", pass_task_id=True)
def wait_external(evt: star.Event, task: star.StarTask):
    import time
    from src.util.util import decompress_bytes_to_str

    print("Waiting for external")
    # wait for external program to be done.
    device_id = evt.data["device_id"]
    io_factory = task.get_io_factory()
    IO_NONEXIST, IO_BUSY, IO_DETACHED, IO_OK = io_factory.get_io_constants()
    device = io_factory.IODevice_FromID(device_id)

    while True:
        status = device.open()
        if status == IO_OK:
            break
        if status == IO_BUSY:
            time.sleep(0.1)
        if status == IO_NONEXIST:
            evt_new = star.Event()
            evt_new.set_target("exit_handler")
            return evt_new
        if status == IO_DETACHED:
            time.sleep(0.1)

    evt_new = star.Event()
    evt_new.data["device"] = device.export()
    evt_new.data["user_nice"] = decompress_bytes_to_str(task.get_user())
    evt_new.set_target("command_loop")
    return evt_new


@star.task("command_disconnect", pass_task_id=True)
def command_disconnect(evt: star.Event, task: star.StarTask):
    res = evt.data.get("device")
    if res is None:
        evt_new = star.Event()
        evt_new.set_target("exit_handler")
        return evt_new

    io_factory = task.get_io_factory()
    IO_NONEXIST, IO_BUSY, IO_DETACHED, IO_OK = io_factory.get_io_constants()
    device = io_factory.IODevice_Import(res)
    out = "--SHELL_DISCONNECT--"

    device.write(out.encode("utf-8"))

    evt_new = star.Event(evt.data)
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
    pgrm.save("shell.star")
