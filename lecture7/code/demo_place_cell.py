"""L7: the PlaceCell tree of btcpp/place_cell.xml, in py_trees.

Usage: demo_place_cell.py FAILURES
The mock pick fails FAILURES times, then succeeds.
"""
import sys

import py_trees
from py_trees.common import Access, Status

failures_left = int(sys.argv[1])


class PickFromTester(py_trees.behaviour.Behaviour):
    def __init__(self, name):
        super().__init__(name)
        self.bb = self.attach_blackboard_client()
        self.bb.register_key("tester", access=Access.READ)

    def update(self):
        global failures_left
        ok = failures_left == 0
        failures_left -= 0 if ok else 1
        result = Status.SUCCESS if ok else Status.FAILURE
        print(f"pick from {self.bb.tester}: {result.name}")
        return result


class PlaceInSlot(py_trees.behaviour.Behaviour):
    def __init__(self, name):
        super().__init__(name)
        self.bb = self.attach_blackboard_client()
        for key in ("agv", "slot"):
            self.bb.register_key(key, access=Access.READ)

    def update(self):
        print(f"place on {self.bb.agv} slot {self.bb.slot}")
        return Status.SUCCESS


root = py_trees.composites.Sequence("PlaceCell", memory=True,
    children=[
        py_trees.decorators.Retry(
            "retry", PickFromTester("pick"), num_failures=3),
        PlaceInSlot("place"),
    ])
for key, value in (("tester", "tester1"), ("agv", "agv1"),
                   ("slot", 2)):
    py_trees.blackboard.Blackboard.set(key, value)
while True:
    root.tick_once()
    if root.status != Status.RUNNING:
        break
print(f"tree: {root.status.name}")
