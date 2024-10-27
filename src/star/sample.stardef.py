import time
import star_components as star


@star.task("input", condition=None)
def input_event(evt: star.Event):
    print("Input Event!")
    a = input("Type in a number: ")
    b = input("Type in a second number: ")

    evt_new = star.Event(a, b)
    evt_new.a = int(a)
    evt_new.b = int(b)
    evt_new.set_target("run_total")

    return evt_new


@star.task("run_total", condition=None)
def run_total(evt):
    total = evt.a + evt.b

    evt_new = star.Event(2, 4)
    evt_new.total = total
    time.sleep(2)
    evt_new.set_target("print_conditional_choice")

    return evt_new


# Condition: total % 2 == 0
@star.task("print_conditional_even", condition=None)
def print_even(evt):
    print(f"The total is even! {evt.total}")

    evt_new = star.Event(0, 1)
    evt_new.total = evt.total
    evt_new.set_target("input")

    return evt_new


@star.task("print_conditional_choice", condition=None)
def print_choice(evt):

    e = star.Event(0, 1)
    e.total = evt.total
    if evt.total % 2 == 0:
        e.set_target("print_conditional_even")

    if evt.total % 2 == 1:
        e.set_target("print_conditional_odd")
    return e


# Condition: total % 2 == 1
@star.task("print_conditional_odd", condition=None)
def print_odd(evt):
    print(f"The total is odd! {evt.total}")

    evt_new = star.Event(0, 0)
    evt_new.total = evt.total
    evt_new.set_target("input")

    return evt_new


if __name__ == "__main__":
    start_event = star.Event(1, 2)
    start_event.set_target("input")
    pgrm = star.compile(start_event=start_event)
    pgrm.save("my_program.star")
