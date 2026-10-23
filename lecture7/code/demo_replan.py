"""L7 demo 5: a replanning trace with mock skills.

Cells, voltages and the arrival order are chosen for this example.
The planner is a stand-in for the L6 planner: it fills the free
slots in order and does no search. Like a classical planner, it
assumes that a cell not yet measured will pass its voltage check.
In this demo, inspection_robot_1 is not in the plan: the mock
factory puts the next cell on a tester as soon as it is free.
"""
import executor as ex
from executor import ROBOT as R

LIMIT = 3  # most replans before the executor stops (chosen)
VOLTS = {"c1": 3.58, "c2": 3.62, "c3": 3.86, "c4": 3.60, "c5": 3.59}
SLOTS = ["s1", "s2", "s3", "s4"]


def problem(facts, volts):
    """Stand-in problem generator: blackboard facts plus results."""
    init = set(facts)
    for cell, v in volts.items():
        init.add(("voltage-ok" if 3.4 <= v <= 3.8 else "voltage-bad",
                  cell))
    return init


def planner(init):
    """Stand-in planner: recycle bad cells, fill slots, ship."""
    steps = []
    free = [s for s in SLOTS if ("slot-free", "agv1", s) in init]
    for f in sorted(f for f in init if f[0] == "holding"):
        c = f[2]  # a cell still held after a stop
        if ("voltage-ok", c) in init:
            s = free.pop(0)
            steps.append(f"(place-in-slot {R} {c} agv1 {s})")
        else:
            steps.append(f"(recycle {R} {c})")
    on_tester = sorted((f[1], f[2]) for f in init
                       if f[0] == "on-tester")
    for c, t in on_tester:
        if ("voltage-bad", c) in init:
            steps += [f"(pick-from-tester {R} {c} {t})",
                      f"(recycle {R} {c})"]
    queued = sorted((f[1], f[2]) for f in init if f[0] == "queued")
    cells = [(c, t) for c, t in on_tester
             if ("voltage-bad", c) not in init] + queued
    if len(cells) < len(free):
        return None  # no plan: not enough cells
    for s, (c, t) in zip(free, cells):
        if ("voltage-ok", c) not in init:
            steps.append(f"(check-voltage {c} {t})")
        steps += [f"(pick-from-tester {R} {c} {t})",
                  f"(place-in-slot {R} {c} agv1 {s})"]
    return steps + ["(move-agv agv1 inspection shipping)"]


def new_cell(cell, t):  # the team's own record of a tester's cell
    facts = ex.get_facts() - {("queued", cell, f"tester{t}")}
    ex.set_facts(facts | {("on-tester", cell, f"tester{t}")},
                 ex.get_volts())


START = [("serves", R, "tester1"), ("serves", R, "tester2"),
         ("hand-free", R), ("agv-at", "agv1", "inspection"),
         ("on-tester", "c1", "tester1"),
         ("on-tester", "c2", "tester2"),
         ("queued", "c3", "tester1"), ("queued", "c4", "tester2"),
         ("queued", "c5", "tester1")] + [
         ("slot-free", "agv1", s) for s in SLOTS]

ex.set_facts(START, {"c1": VOLTS["c1"], "c2": VOLTS["c2"]})
factory = ex.MockFactory({1: "c1", 2: "c2"},
                         {1: ["c3", "c5"], 2: ["c4"]}, VOLTS)
factory.on_new_cell = new_cell
ex.LOG = lambda line: print("  " + line.split(": ", 1)[1])
replans, before = 0, None
while True:
    init = problem(ex.get_facts(), ex.get_volts())
    ex.set_facts(init, ex.get_volts())  # results go on the blackboard
    if before is not None:
        print("new problem, facts that changed:")
        for f in sorted(init - before):
            print("  + " + ex.fact_text(f))
        for f in sorted(before - init):
            print("  - " + ex.fact_text(f))
    steps = planner(init)
    if steps is None:
        print("no plan: stop and report")
        break
    print(f"plan {replans + 1}, {len(steps)} steps:")
    for i, step in enumerate(steps, start=1):
        print(f"  {i:>2} {step}")
    print(f"run plan {replans + 1}:")
    status, _ = ex.run(ex.build_tree(steps, factory), running=False)
    if status.name == "SUCCESS":
        kit = [factory.tray[(1, n)] for n in range(1, 5)]
        total = sum(VOLTS[c] for c in kit)
        print(f"done: agv1 shipped {' '.join(kit)} ({total:.2f} V),"
              f" replans {replans}")
        break
    replans += 1
    print(f"stopped between steps; replans {replans} of {LIMIT}")
    if replans > LIMIT:
        print("replan limit passed: stop and report")
        break
    before = init
