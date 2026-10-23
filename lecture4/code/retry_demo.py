"""Retry around a pick that fails once; memory vs no memory.

The leaves are stand-ins with no robot: each action leaf returns
RUNNING for one tick, then its next scripted result.
"""
import py_trees
from py_trees.common import Status


class Step(py_trees.behaviour.Behaviour):
    """RUNNING for `run_ticks` ticks, then the next of `results`."""

    def __init__(self, name, results, run_ticks=1):
        super().__init__(name)
        self.results = list(results)
        self.run_ticks = run_ticks
        self.calls = 0

    def initialise(self):
        self.left = self.run_ticks

    def update(self):
        self.calls += 1
        if self.left > 0:
            self.left -= 1
            return Status.RUNNING
        if len(self.results) > 1:
            return self.results.pop(0)
        return self.results[0]


def build(memory):
    check = Step("check_tester_ok", [Status.SUCCESS], run_ticks=0)
    pick = Step("pick_from_tester",
                [Status.FAILURE, Status.SUCCESS], run_ticks=1)
    place = Step("place_in_slot", [Status.SUCCESS], run_ticks=1)
    retry = py_trees.decorators.Retry("retry_pick", pick,
                                      num_failures=2)
    root = py_trees.composites.Sequence(
        "move_cell", memory=memory, children=[check, retry, place])
    return root, check, pick, place


for memory in (True, False):
    root, check, pick, place = build(memory)
    tree = py_trees.trees.BehaviourTree(root)
    print(f"memory={memory}")
    for i in range(1, 15):
        tree.tick()
        print(f"  tick {i}: root={root.status.name}"
              f" check={check.status.name}"
              f" pick={pick.status.name}"
              f" place={place.status.name}")
        if root.status != Status.RUNNING:
            break
    print(f"  check_tester_ok updated {check.calls} times,"
          f" pick updated {pick.calls} times")
