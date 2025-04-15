# Framework for *STAR* programs that run on the OS.

The Starfish OS does not run actual executables built by `gcc` or other compilers. Rather, it runs a special python program that is broken down into pieces (called *tasks*) that can be distributed across the network. Each task receives and sends out an event.

> Currently, tasks must send out an event. Work will be done in the future to allow for terminating tasks.

Each program is then broken down into tasks which are marked by the `star.task()` or `star.conditional_task()` decorator. This tells the compiler what each task is for the event targets. The code inside the task can be whatever one wants. There are a few small rules for each task:
1. Each task is stateless! It must not rely on anything external to the task that maintains state (meaning: no global variables) 
2. The task must try to run as fast as possible (try less than 100msec) to free up the OS for other tasks.
3. The task must include required imports inside the task


An example task

``` python
@star.task("input")
def input_event(evt: star.Event): # Every task has one parameter for event (unless for a complex task which will be explained later)
    print("Input Event!")
    a = input("Type in a number: ")
    b = input("Type in a second number: ")

    evt_new = star.Event()
    data = {
        "a": int(a),
        "b": int(b),
    }
    evt_new.data = data
    evt_new.set_target("run_total") # Create a new event and mark it for the "run_total" task in this program. You can only send events to other tasks in the same program

    return evt_new

```


A task can also be a "conditional_task" which means that it only runs when an event matches a certain condition. Below are two tasks, both the same name but different conditions. The condition is code-in-a-string being a lambda function that returns True/False

``` python
@star.conditional_task(
    "print_conditional", "lambda evt: evt.data.get('total') % 2 == 0"
)
def print_even(evt):
    total = evt.data.get("total")
    print(f"The total is even! {total}")

    evt_new = star.Event(data={"total": total})
    evt_new.set_target("input")

    return evt_new

@star.conditional_task(
    "print_conditional", "lambda evt: evt.data.get('total') % 2 == 1"
)
def print_odd(evt):
    print(f"The total is odd! {evt.data.get('total')}")

    evt_new = star.Event()
    evt_new.set_target("input")

    return evt_new

```
<br>
<br>

# OS Features in a task

In addition to normal program code in each task, one can also use some special calls (think syscalls). 


1. File Operations - StarfishOS Files (Future. Not implemented yet)
2. I/O Operations - StarfishOS I/O (Future. Not implemented yet) 

> Unfortunately, the system originally supported tasks spawning additional tasks with the below commands.
> However, in developing the dropout algorithm (where nodes can die and have the process respawned),
> when making the part that transfers process context, it breaks the current design of awaited events.
> Due to time constraints, I am dropping the below features. It still is possible to do but requires engine rework
> 
> 1. Dispatching other events without awaiting
> 2. Dispatching other events but waiting for feedback
> 3. Dispatching a group of events and waiting for them all to complete
> 


#### 1 & 2 - File and I/O 
To be built! 

# Compiling 

Once you have your program, it must be "compiled". Unlike an actual compiler, this "compiler" simply catalogs the tasks and creates a binary file that makes it easy for the OS to parse. That's it.

To compile, one only needs the following inside the same file the tasks are located:

``` python
if __name__ == "__main__":
    start_event = star.Event()
    start_event.set_target("start-task-name-here")
    pgrm = star.compile(start_event=start_event)
    pgrm.save("program.star")
```

It will take the rest of the tasks in the file and create a STAR file from it. Note: it finds the tasks in that immediate file. This means one python file per program. You can't compile two programs in one python file. Note: This must be in a `__name__ == "__main__"` thing or else bad things will happen!

If you want logging feedback, stick this crazy long logging thing before the above (in the `__name__ == __main__`):

``` python 
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
```

# Final Notes

Look at the example programs. 
1. `sample.stardef.py` is a simple example. Has unconditional (normal) tasks and conditional tasks. No OS features used
2. `list_dist.stardef.py` is another example.
3. `file_reader.py` is an example for file usage (although not using the OS features just yet)

