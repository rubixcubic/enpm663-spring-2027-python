"""L7 demo 1: build a tree from a five-step plan and tick it.

Usage: demo_factory.py build | tick | trace | unknown | nomemory |
       noguard
Cells, voltages and slots are chosen for this example. Slots s1 and
s2 were filled earlier; c3 and c4 wait on the testers, measured.
"""
import sys

import py_trees

import executor as ex
from executor import ROBOT

PLAN = [
    f"(pick-from-tester {ROBOT} c3 tester1)",
    f"(place-in-slot {ROBOT} c3 agv1 s3)",
    f"(pick-from-tester {ROBOT} c4 tester2)",
    f"(place-in-slot {ROBOT} c4 agv1 s4)",
    "(move-agv agv1 inspection shipping)",
]
START = [
    ("serves", ROBOT, "tester1"), ("serves", ROBOT, "tester2"),
    ("hand-free", ROBOT), ("agv-at", "agv1", "inspection"),
    ("on-tester", "c3", "tester1"), ("voltage-ok", "c3"),
    ("on-tester", "c4", "tester2"), ("voltage-ok", "c4"),
    ("slot-free", "agv1", "s3"), ("slot-free", "agv1", "s4"),
]


def setup():
    ex.set_facts(START)
    return ex.MockFactory({1: "c3", 2: "c4"}, {1: [], 2: []},
                          {"c3": 3.62, "c4": 3.55})


def main(mode):
    factory = setup()
    if mode == "build":
        print("plan:")
        for i, action in enumerate(PLAN, start=1):
            print(f"  {i} {action}")
        root = ex.build_tree(PLAN, factory)
        print(f"tree: {len(root.children)} subtrees under "
              f"'{root.name}', memory={root.memory}")
    elif mode == "tick":
        root = ex.build_tree(PLAN, factory)
        root.tick_once()
        root.tick_once()
        print("after tick 2 (steps 3 to 5 not started yet):")
        print(py_trees.display.ascii_tree(root, show_status=True)
              .split("    {-} 3")[0].rstrip())
    elif mode == "trace":
        root = ex.build_tree(PLAN, factory)
        status, ticks = ex.run(root)
        print(f"plan {status.name} after {ticks} ticks; "
              f"{factory.goals} goals sent")
    elif mode == "unknown":
        typo = PLAN[:4] + ["(move-avg agv1 inspection shipping)"]
        try:
            ex.build_tree(typo, factory)
        except KeyError as err:
            print(f"build failed: {err.args[0]}")
            print(f"goals sent: {factory.goals}")
    elif mode == "nomemory":
        root = ex.build_tree(PLAN, factory)
        root.memory = False  # the bug: a Sequence without memory
        status, ticks = ex.run(root)
        print(f"plan {status.name} after {ticks} ticks; "
              f"{factory.goals} goals sent")
    elif mode == "noguard":
        ex.Guard.update = lambda self: py_trees.common.Status.SUCCESS
        root = ex.build_tree(PLAN, factory)
        root.memory = False  # the same bug, and guards that pass
        status, ticks = ex.run(root, max_ticks=6)
        print(f"plan {status.name} after {ticks} ticks; "
              f"{factory.goals} goals sent")


if __name__ == "__main__":
    main(sys.argv[1])
