"""The status a composite or decorator returns, from its children.

Each leaf is a stand-in that returns one fixed status. Each case
builds a fresh tree, ticks it once and prints every child's status
and the parent's. INVALID means the child was not ticked.
"""
import time

import py_trees
from py_trees.common import Status
from py_trees.composites import Selector, Sequence
from py_trees.decorators import FailureIsSuccess, Inverter, Timeout

S, F, R = Status.SUCCESS, Status.FAILURE, Status.RUNNING


class Fixed(py_trees.behaviour.Behaviour):
    """A stand-in leaf that always returns `status`."""

    def __init__(self, name, status):
        super().__init__(name)
        self.fixed = status

    def update(self):
        return self.fixed


def show(label, parent, leaves):
    parent.tick_once()
    kids = " ".join(f"{k.name}={k.status.name}" for k in leaves)
    print(f"{label}: {kids} -> {parent.status.name}")


print("Sequence move_cell (memory=True)")
for i, case in enumerate(((S, S, S), (S, F, S), (S, R, S)), 1):
    leaves = [Fixed(n, s) for n, s in
              zip(("pick", "place", "update"), case)]
    show(f"  {i}", Sequence("move_cell", True, leaves), leaves)

print("Selector place_or_recycle (memory=False)")
for i, case in enumerate(((S, S), (F, S), (F, F)), 4):
    leaves = [Fixed(n, s) for n, s in
              zip(("place_if_good", "recycle"), case)]
    root = Selector("place_or_recycle", False, leaves)
    show(f"  {i}", root, leaves)

print("Decorators")
for deco, s in ((Inverter, S), (Inverter, F), (Inverter, R),
                (FailureIsSuccess, F)):
    leaf = Fixed("child", s)
    show(f"  {deco.__name__}", deco(deco.__name__, leaf), [leaf])

leaf = Fixed("child", R)
timeout = Timeout("timeout", leaf, duration=0.2)
show("  Timeout tick 1", timeout, [leaf])
time.sleep(0.3)
show("  Timeout tick 2, after 0.3 s", timeout, [leaf])
