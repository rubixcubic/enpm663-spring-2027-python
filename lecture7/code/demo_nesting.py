"""L7 demo 4: Retry(Timeout(act)) against Timeout(Retry(act)).

Usage: demo_nesting.py hang | fail
'hang': the act never finishes. 'fail': each attempt fails after
0.15 s. Limit 0.2 s, num_failures=3, tick period 0.02 s, 5 runs of
each: all chosen for this demo.
"""
import sys
import time

import py_trees
from py_trees.common import Status
from py_trees.decorators import Retry, Timeout

LIMIT, TRIES, TICK, RUNS = 0.2, 3, 0.02, 5


class MockAct(py_trees.behaviour.Behaviour):
    def __init__(self, fail_after):
        super().__init__("act")
        self.fail_after, self.attempts = fail_after, 0
        self.starts = []  # when each attempt started

    def initialise(self):
        self.attempts += 1
        self.start = time.monotonic()
        self.starts.append(self.start)

    def update(self):
        if self.fail_after is None:  # never finishes
            return Status.RUNNING
        if time.monotonic() - self.start < self.fail_after:
            return Status.RUNNING
        return Status.FAILURE


def trial(order, fail_after):
    act = MockAct(fail_after)
    if order == "Retry(Timeout(act))":
        root = Retry("retry", Timeout("timeout", act, LIMIT), TRIES)
    else:
        root = Timeout("timeout", Retry("retry", act, TRIES), LIMIT)
    start = time.monotonic()
    while True:
        root.tick_once()
        if root.status != Status.RUNNING:
            starts = [t - start for t in act.starts]
            return time.monotonic() - start, act.attempts, starts
        time.sleep(TICK)


fail_after = None if sys.argv[1] == "hang" else 0.15
for order in ("Retry(Timeout(act))", "Timeout(Retry(act))"):
    times, tries, starts = zip(*(trial(order, fail_after)
                                 for _ in range(RUNS)))
    low, high = f"{min(times):.2f}", f"{max(times):.2f}"
    span = low if low == high else f"{low} to {high}"
    print(f"{order}: FAILURE after {span} s, "
          f"attempts {sorted(set(tries))}")
    if "--starts" in sys.argv:  # run 1, for the figure
        print("  run 1 attempts started at "
              + ", ".join(f"{t:.2f}" for t in starts[0])
              + f" s, ended at {times[0]:.2f} s")
