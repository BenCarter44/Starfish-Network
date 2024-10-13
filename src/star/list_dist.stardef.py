import time
import star_components as star
import star_os


@star.task("input", condition=None, pass_task_id=True)
def input_event(evt: star.Event, task_id: star.TaskIdentifier):
    a = input("Type in a number: ")
    b = input("Type in a second number: ")

    evt_new = star.Event(a, b)
    evt_new.set_target("cast_numbers")

    # print("Await!")
    awaitable = star.AwaitEvent(evt_new, task_id)
    evt_out = awaitable.wait_for_result(timeout=30)
    # print("Done Await!")

    evt_new = star.Event(evt_out.a, evt_out.b)
    evt_new.set_target("run_total")

    return evt_new


@star.task("cast_numbers", condition=None)
def cast_numbers(evt):

    evt.a = int(evt.a)
    evt.b = int(evt.b)

    return evt


@star.task("run_total", condition=None)
def run_total(evt):
    total = evt.a + evt.b

    # f = star_os.open("/path/to/distributed/file")
    # f.close()

    # d = star_os.open_datapipe("/path/to/data/pipe.pipe")
    # d.close()

    evt.total = total

    if evt.system is None:
        evt.set_target("print_conditional")

    # evt_new = star.Event(2, 4)
    # evt_new.total = total
    # time.sleep(5)
    # evt_new.set_target("print_conditional")

    return evt


# Condition: total % 2 == 0
@star.task("print_conditional", condition=lambda evt: evt.total % 2 == 0)
def print_even(evt):
    print(f"The total is even! {evt.total}")

    evt_new = star.Event(0, 1)
    evt_new.total = evt.total
    evt_new.set_target("list_intro")

    return evt_new


# Condition: total % 2 == 1
@star.task("print_conditional", condition=lambda evt: evt.total % 2 == 1)
def print_odd(evt):
    print(f"The total is odd! {evt.total}")

    evt_new = star.Event(0, 0)
    evt_new.total = evt.total
    evt_new.set_target("list_intro")

    return evt_new


@star.task("to_capital", condition=None)
def to_cap(evt: star.Event):
    evt.b = evt.b.upper()
    return evt


# Condition: None
@star.task("list_intro", condition=None, pass_task_id=True)
def list_intro(evt, task_id: star.TaskIdentifier):
    i = input("Please type a string: ")

    await_group = star.AwaitGroup(originating_task=task_id)
    for index, token in enumerate(i):
        # create a await event for each.
        evt = star.Event(index, token)
        evt.set_target("to_capital")
        await_group.add_event(evt)

    results = await_group.wait_result_for_all(timeout=30)
    string = list(" " * len(i))
    for result in results:
        string[result.a] = result.b

    await_group.close()

    string = "".join(string)  # type: ignore
    print(string)
    evt_new = star.Event()
    evt_new.set_target("input")
    return evt_new


if __name__ == "__main__":
    start_event = star.Event(1, 2)
    start_event.set_target("input")
    pgrm = star.compile(start_event=start_event)
    pgrm.save("my_list_program.star")
