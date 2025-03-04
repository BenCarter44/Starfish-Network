try:
    from ..src.KernelCommands import CapturingArgumentParser
    from ..src.core import star_components as star
except:
    from core import star_components as star
    from KernelCommands import CapturingArgumentParser


class CommandProcessor:
    def __init__(self, data):
        self.parser = CapturingArgumentParser(
            prog="fish",
            description="Starfish OS Bash (Fish)",
            epilog="StarfishOS fish",
            exit_on_error=False,
        )
        subparsers = self.parser.add_subparsers(dest="command")

        # ls command
        ls_parser = subparsers.add_parser(
            "ls", description="List contents of directory"
        )
        ls_parser.add_argument(
            "-a", "--all", action="store_true", help="List all users files"
        )
        ls_parser.add_argument(
            "-d", "--device", action="store_true", help="List devices"
        )
        ls_parser.set_defaults(func=self.ls)

        # echo command
        echo_parser = subparsers.add_parser("echo", description="Print text")
        echo_parser.add_argument("text", type=str, help="Text to print")
        echo_parser.set_defaults(func=self.echo)

        # write command
        write_parser = subparsers.add_parser(
            "write", description="Write text to a file"
        )
        write_parser.add_argument("-f", "--file", type=str, help="File to write to")
        write_parser.add_argument("text", type=str, help="Text to write")
        write_parser.set_defaults(func=self.write)

        # cat command
        cat_parser = subparsers.add_parser("cat", description="Display file contents")
        cat_parser.add_argument("file", type=str, help="File to read")
        cat_parser.set_defaults(func=self.cat)

        # run command
        run_parser = subparsers.add_parser("run", description="Run a program")
        run_parser.add_argument("program", type=str, help="Program to execute")
        run_parser.set_defaults(func=self.run)

        # disconnect command
        disconnect_parser = subparsers.add_parser("disconnect", help="Exit the CLI")
        disconnect_parser.set_defaults(func=self.disconnect)
        self.data = data

    def ls(self, args):
        evt = star.Event(self.data)
        evt.set_target("command_list")
        evt.data["all"] = args.all
        evt.data["device_flag"] = args.device
        return evt

    def echo(self, args):
        evt = star.Event(self.data)
        evt.set_target("command_echo")
        evt.data["text"] = args.text
        return evt

    def write(self, args):
        evt = star.Event(self.data)
        evt.set_target("command_write")
        evt.data["text"] = args.text
        evt.data["file"] = args.file
        return evt

    def cat(self, args):
        evt = star.Event(self.data)
        evt.set_target("command_cat")
        evt.data["file"] = args.file
        return evt

    def run(self, args):
        evt = star.Event(self.data)
        evt.set_target("command_run")
        evt.data["program"] = args.program
        return evt

    def disconnect(self, args):
        evt = star.Event(self.data)
        evt.set_target("command_disconnect")
        return evt
