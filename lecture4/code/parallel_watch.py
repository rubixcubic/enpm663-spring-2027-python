"""A parallel that watches the tester while it waits for readings.

Stand-in tester (values chosen for this example): on tick 1 it
reads 3.61 V and is OPERATIONAL; from tick 2 on it reads -1.0 V and
is MALFUNCTIONING, as ARIAC's tester does during that challenge.
wait_for_voltage averages one reading per tick and needs five.
The parallel succeeds when wait_for_voltage succeeds; it is run
with synchronise=True (the py_trees default) and with False.
"""
import py_trees
from py_trees.common import ParallelPolicy, Status

TESTER = [(3.61, "OPERATIONAL")] + [(-1.0, "MALFUNCTIONING")] * 9


class TesterOk(py_trees.behaviour.Behaviour):
    """Condition: SUCCESS while the tester is OPERATIONAL."""

    def __init__(self, clock):
        super().__init__("tester_ok")
        self.clock = clock
        self.checks = 0

    def update(self):
        self.checks += 1
        _, state = TESTER[self.clock["tick"]]
        if state == "OPERATIONAL":
            return Status.SUCCESS
        return Status.FAILURE


class WaitForVoltage(py_trees.behaviour.Behaviour):
    """Collects one reading per tick; SUCCESS after five."""

    def __init__(self, clock):
        super().__init__("wait_for_voltage")
        self.clock = clock
        self.readings = []

    def initialise(self):
        self.readings = []

    def update(self):
        self.readings.append(TESTER[self.clock["tick"]][0])
        if len(self.readings) < 5:
            return Status.RUNNING
        return Status.SUCCESS


for sync in (True, False):
    clock = {"tick": 0}
    ok, wait = TesterOk(clock), WaitForVoltage(clock)
    policy = ParallelPolicy.SuccessOnSelected(
        [wait], synchronise=sync)
    root = py_trees.composites.Parallel(
        "wait_for_reading", policy, children=[ok, wait])
    print(f"synchronise={sync}")
    for tick in range(1, 8):
        clock["tick"] = tick - 1
        root.tick_once()
        print(f"  tick {tick}: tester {TESTER[tick - 1][1]:<14}"
              f" ok={ok.status.name:<7} wait={wait.status.name:<7}"
              f" -> {root.status.name}")
        if root.status != Status.RUNNING:
            break
    print(f"  tester_ok checked {ok.checks} times")
    if root.status == Status.SUCCESS:
        mean = sum(wait.readings) / len(wait.readings)
        print(f"  average of {len(wait.readings)} readings: "
              f"{mean:.3f} V")
