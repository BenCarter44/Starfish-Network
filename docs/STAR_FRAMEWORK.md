# Framework for *STAR* programs that run on the OS.

The Starfish OS does not run actual executables built by `gcc` or other compilers. Rather, it runs a special python program that is broken down into pieces (called *tasks*) that can be distributed across the network. Each task receives and sends out an event.

> Currently, tasks must send out an event. Work will be done in the future to allow for terminating tasks.

Each program is then broken down into tasks which are marked by the `star.task()` or `star.conditional_task()` decorator. This tells the compiler what each task is for the event targets. The code inside the task can be whatever one wants. There are a few small rules for each task:
1. Each task is stateless! It must not rely on anything external to the task that maintains state (meaning: no global variables) 
2. The task must try to run as fast as possible (try less than 100msec) to free up the OS for other tasks.
3. The task must include required imports inside the task

**Run `simple_executor.py <PATH TO STAR PROGRAM>` to run a STAR program.**

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

1. Dispatching other events without awaiting
2. Dispatching other events but waiting for feedback
3. Dispatching a group of events and waiting for them all to complete
4. File Operations - StarfishOS Files (Future. Not implemented yet)
5. I/O Operations - StarfishOS I/O (Future. Not implemented yet) 

For 1-3, when used, it makes the task become a "complex task" and requires the originating task object to be passed. This object should not be tampered with. It carries the necessary data of the current task for the syscalls. 
<br>
<br>
Below is an example of a task with the originating task passed in as the second parameter. Notice the `pass_task_id` flag on the `star.task` as `star.AwaitEvent()` requires it.

``` python

@star.task("input", pass_task_id=True)
def input_event(evt: star.Event, task_id: star.StarTask):
    a = input("Type in a number: ")
    b = input("Type in a second number: ")

    evt_new = star.Event()
    evt_new.data = {"a": a, "b": b}
    evt_new.set_target("cast_numbers")

    # print("Await!")
    awaitable = star.AwaitEvent(evt_new, task_id)
    evt_out = awaitable.wait_for_result(timeout=30)
    # print("Done Await!")

    evt_new = star.Event()
    evt_new.data = {"a": evt_out.data["a"], "b": evt_out.data["b"]}
    evt_new.set_target("run_total")

    return evt_new
```

#### 1 - Dispatching other events without awaiting
For fire and forget, use the function call `star.dispatch_event(event, task)` inside the task.

#### 2 - Dispatching other events with await
This is not to be confused with asyncio's `await`. This means simply to fire an event and wait for the event's target task to complete and give a response. 

Create an AwaitEvent object with `a = star.AwaitEvent(event, task)` <br>
Wait for the result: `a.wait_for_result(timeout=5)` which returns an event. See the above example that uses `star.AwaitEvent()`


Now, to do this correctly, the receiving task **must not change the target or any other event parameter except data**. It must return the same event it was passed in. This allows the OS to route it back to the correct place. An example below. This "cast_numbers" task can now be used in an `AwaitEvent`

``` python
@star.task("cast_numbers")
def cast_numbers(evt):
    evt.data["a"] = int(evt.data["a"])
    evt.data["b"] = int(evt.data["b"])
    return evt
```

#### 3 - Dispatching a group of events and waiting for them to all complete
This works great for distributing work in a list for instance. It's exactly the same as above with `AwaitEvent` but `AwaitGroup` is used instead. 


An example that distributes each letter of a string to a "to_capital" task and then waits for all to come back.

``` python
@star.task("list_intro", pass_task_id=True)
def list_intro(evt, task_id: star.StarTask):
    i = input("Please type a string: ")

    await_group = star.AwaitGroup(originating_task=task_id)
    for index, token in enumerate(i):
        # create a await event for each.
        evt = star.Event()
        evt.data["index"] = index
        evt.data["token"] = token
        evt.set_target("to_capital")
        await_group.add_event(evt)

    results = await_group.wait_result_for_all(timeout=30)
    string = list(" " * len(i))
    for result in results:
        string[result.data["index"]] = result.data["token"]

    await_group.close()

    string = "".join(string)  # type: ignore
    print(string)
    evt_new = star.Event()
    evt_new.set_target("input")
    return evt_new
```

The target task must be formatted the same as seen previously without touching the target. The received event is the same event that is sent out (with the data parameter changed).

#### 4 & 5 - File and I/O 
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
2. `list_dist.stardef.py` is an example that demonstrates OS features for events.
3. `file_reader.py` is an example for file usage (although not using the OS features just yet)

**Run `simple_executor.py <PATH TO STAR PROGRAM>` to run a STAR program.**
