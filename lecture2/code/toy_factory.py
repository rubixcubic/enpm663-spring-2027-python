#!/usr/bin/env python3
"""A toy Task 1 run, three ways: plan only, react only, three layers.

A toy, not ARIAC: plain Python, no ROS, no simulator, one robot
action at a time. It keeps these ARIAC 2025 rules (branch ariac2025):
  - Li-Ion cell: 3.6 V nominal, +/-0.2 V per cell, +/-0.15 V per kit
    of four (ariac_interfaces/msg/CellTypes.msg).
  - Cell voltages spread with a standard deviation of 0.1 V
    (ariac_plugins/include/ariac_plugins/cell_feed_plugin.hpp).
  - Tester noise 0.05 V (ariac_gz/models/voltage_tester/model.sdf);
    an empty tester reads about 0 V; a new reading every 0.1 s; a
    malfunctioning tester reports -1 V with status MALFUNCTIONING
    (ariac_plugins/src/voltage_tester_plugin.cpp).
Everything else (durations, failure rate, cell count) is chosen for
this example. Fixed seeds make every run repeat exactly.
"""
import argparse
import random

NOMINAL = 3.6       # V, Li-Ion nominal (CellTypes.msg)
CELL_TOL = 0.2      # V, one cell (CellTypes.msg)
KIT_TOL = 0.15      # V, kit of four (CellTypes.msg)
CELL_SPREAD = 0.1   # V (cell_feed_plugin.hpp)
NOISE = 0.05        # V (voltage_tester/model.sdf)
OPERATIONAL, MALFUNCTIONING = 1, 2      # OperationStates.msg
OK = "SUCCESS"

# Toy durations in seconds, chosen for this example
T_PICK, T_PLACE, T_MOVE, T_TRAY, T_BIN, T_SHIP = 4, 3, 4, 6, 4, 10
T_READ = 0.1        # one reading (ARIAC publishes every 0.1 s)
N_READS = 10        # readings averaged per cell
MARGIN = 0.05       # V, the planner stays this far inside the window
SLACK = 0.05        # V, extra room per kit slot still empty


class Factory:
    """The world: conveyor, two testers, AGV trays, a clock."""

    def __init__(self, a):
        rng = random.Random(a.seed)
        self.v = [round(rng.gauss(NOMINAL, CELL_SPREAD), 2)
                  for _ in range(a.cells)]
        self.noise = random.Random(a.seed + 1)
        self.grasp = random.Random(a.seed + 2)
        self.a, self.t, self.log = a, 0.0, []
        self.queue = list(range(1, a.cells + 1))  # cells to pick
        self.held = None                 # cell in the gripper
        self.tester = {1: None, 2: None}  # cell in each tester
        self.tray = {1: [], 2: [], 3: []}  # cells on each AGV
        self.binned = []                 # cells in the recycling bin

    def volts(self, cell):
        return self.v[cell - 1]

    def note(self, text):
        self.log.append(f"{self.t:6.1f} s  {text}")

    # ARIAC stand-in: the tester status and one reading
    def status(self, n):
        a = self.a
        down = (a.malfunction and n == a.tester
                and a.start <= self.t < a.start + a.duration)
        return MALFUNCTIONING if down else OPERATIONAL

    def free(self, n):
        """Tester n is empty and working."""
        empty = self.tester[n] is None
        return empty and self.status(n) == OPERATIONAL

    def read(self, n):
        """One reading of tester n: (voltage, status)."""
        self.t += T_READ
        if self.status(n) == MALFUNCTIONING:
            return -1.0, MALFUNCTIONING
        cell = self.tester[n]
        v = 0.0 if cell is None else self.volts(cell)
        return v + self.noise.gauss(0.0, NOISE), OPERATIONAL

    # Skills: the course skills package stand-in (arms only).
    # Each returns SUCCESS or a failure reason. None retries.
    def pick_from_conveyor(self):
        self.t += T_PICK
        if self.held is not None:
            return "GRIPPER_FULL"
        if not self.queue:
            return "NO_CELL_LEFT"
        if self.grasp.random() < self.a.pick_fail:
            return "GRASP_FAILED"
        self.held = self.queue.pop(0)
        return OK

    def place_in_tester(self, n):
        self.t += T_PLACE
        if self.held is None or self.tester[n] is not None:
            return "NOTHING_TO_PLACE"
        self.tester[n], self.held = self.held, None
        return OK

    def tester_to_tester(self, src, dst):
        self.t += T_MOVE
        self.tester[dst], self.tester[src] = self.tester[src], None
        return OK

    def tester_to_tray(self, n, agv):
        self.t += T_TRAY
        if self.tester[n] is None:
            return "TESTER_EMPTY"
        self.tray[agv].append(self.tester[n])
        self.tester[n] = None
        return OK

    def tester_to_bin(self, n):
        self.t += T_BIN
        if self.tester[n] is None:
            return "TESTER_EMPTY"
        self.binned.append(self.tester[n])
        self.tester[n] = None
        return OK

    # ARIAC stand-in for /agvN/move and the kit submission check
    def ship(self, agv):
        self.t += T_SHIP
        cells = [self.volts(c) for c in self.tray[agv]]
        total = round(sum(cells), 2)  # volts have 2 decimals
        if len(cells) != 4:
            return f"kit rejected: {len(cells)} cells, a kit needs 4"
        if any(round(abs(v - NOMINAL), 2) > CELL_TOL for v in cells):
            return "kit rejected: a cell is outside 3.4 to 3.8 V"
        if round(abs(total - 4 * NOMINAL), 2) > KIT_TOL:
            return (f"kit rejected: total {total:.2f} V is outside"
                    " 14.25 to 14.55 V")
        return f"kit accepted: total {total:.2f} V"


def average(f, n):
    """Average N_READS readings of tester n, and the worst status."""
    vals, worst = [], OPERATIONAL
    for _ in range(N_READS):
        v, s = f.read(n)
        vals.append(v)
        worst = max(worst, s)
    return sum(vals) / len(vals), worst


def in_range(v):
    return abs(v - NOMINAL) <= CELL_TOL


def sort_cell(f, n, v):
    """Tray if reading v is in range, else the bin. Logs the step."""
    cell = f.tester[n]
    name = f"cell {cell}" if cell else "no cell"
    where = "AGV 1" if in_range(v) else "bin"
    f.note(f"{name}: tester {n} reads {v:5.2f} V -> {where}")
    if in_range(v):
        return f.tester_to_tray(n, agv=1)
    return f.tester_to_bin(n)


# Architecture 1: plan only ---------------------------------------
def plan_only(f):
    """One fixed plan, made at t = 0. It never checks a result."""
    plan = [1 + k % 2 for k in range(len(f.queue))]  # testers 1, 2, 1
    for n in plan:
        if len(f.tray[1]) == 4:
            break
        f.pick_from_conveyor()       # result not checked
        f.place_in_tester(n)
        v, _ = average(f, n)         # status not checked
        sort_cell(f, n, v)
    return f.ship(1)


# Architecture 2: react only --------------------------------------
def react_only(f):
    """Rules on what the sensors show now. No plan, no memory."""
    while f.t < f.a.limit:
        if len(f.tray[1]) == 4:                       # rule 1
            return f.ship(1)
        fired = False
        for n in (1, 2):
            v, s = f.read(n)
            cell, other = f.tester[n], 3 - n
            if cell and s == MALFUNCTIONING and f.free(other):
                f.note(f"cell {cell}: tester {n} reads -1 V"
                       f" -> tester {other}")         # rule 2
                f.tester_to_tester(n, other)
                fired = True
            elif cell and s == OPERATIONAL:           # rule 3
                sort_cell(f, n, v)
                fired = True
        free = [n for n in (1, 2) if f.free(n)]
        if f.queue and free:                          # rule 4
            if f.pick_from_conveyor() == OK:
                f.place_in_tester(free[0])
            fired = True
        if not fired:
            f.t += T_READ                             # wait
    return "not finished: time limit reached"


# Architecture 3: three layers ------------------------------------
class Planner:
    """Deliberative layer: which tester, and where each cell goes."""

    def __init__(self):
        self.kit = []          # measured voltages placed on AGV 1
        self.down = set()      # testers reported MALFUNCTIONING
        self.spare = 0         # in-range cells kept for later kits
        self.last = 2

    def choose_tester(self):
        for n in (3 - self.last, self.last):    # alternate
            if n not in self.down:
                self.last = n
                return n
        return None

    def destination(self, v):
        if not in_range(v):
            return "bin"
        k = len(self.kit) + 1                   # slot this cell fills
        off = sum(self.kit) + v - k * NOMINAL   # offset from nominal
        room = KIT_TOL - MARGIN + SLACK * (4 - k)
        if abs(off) <= room:
            self.kit.append(v)
            return "AGV 1"
        self.spare += 1        # in range: saved for a later kit
        return "AGV 2" if self.spare <= 4 else "AGV 3"


class Executive:
    """Runs each step, checks every result, retries or reports up."""

    def __init__(self, f, retries=2):
        self.f, self.retries = f, retries

    def pick(self):
        for attempt in range(1 + self.retries):
            r = self.f.pick_from_conveyor()
            if r != "GRASP_FAILED":
                return r                        # SUCCESS, or no cell
            self.f.note(f"pick: {r}, attempt {attempt + 1}"
                        f" of {1 + self.retries}")
        return f"{r} {1 + self.retries} times"

    def test_cell(self, n):
        """Pick a cell, test it at tester n. Returns a report."""
        f = self.f
        r = self.pick()
        if r != OK:
            return {"error": f"pick: {r}"}
        f.place_in_tester(n)
        v, s = average(f, n)
        down = set()
        if s == MALFUNCTIONING:                 # seen here
            down.add(n)
            f.note(f"cell {f.tester[n]}: tester {n} MALFUNCTIONING"
                   f" -> move to tester {3 - n}")
            f.tester_to_tester(n, 3 - n)        # handled here
            n = 3 - n
            v, s = average(f, n)
        while s == MALFUNCTIONING and f.t < f.a.limit:
            f.t += 1.0                          # both down: wait
            v, s = average(f, n)
        return {"tester": n, "volts": v, "down": down}

    def unload(self, n, where):
        if where == "bin":
            return self.f.tester_to_bin(n)
        return self.f.tester_to_tray(n, agv=int(where[-1]))


def three_layers(f):
    planner, ex = Planner(), Executive(f, retries=f.a.retries)
    while len(planner.kit) < 4:
        if f.t >= f.a.limit:
            return "not finished: time limit reached"
        for n in sorted(planner.down):          # check for recovery
            if f.read(n)[1] == OPERATIONAL:
                planner.down.discard(n)
                f.note(f"tester {n} OPERATIONAL again")
        n = planner.choose_tester()
        if n is None:                           # both down: wait
            f.t += 1.0
            continue
        report = ex.test_cell(n)
        if "error" in report:                   # status moves up
            return f"stopped cleanly: {report['error']}"
        planner.down |= report["down"]          # status moves up
        n, v = report["tester"], report["volts"]
        where = planner.destination(v)
        f.note(f"cell {f.tester[n]}: tester {n} reads {v:5.2f} V"
               f" -> {where}")
        ex.unload(n, where)
    return f.ship(1)


ARCHS = {"plan only": plan_only, "react only": react_only,
         "three layers": three_layers}


def run(name, a):
    f = Factory(a)
    verdict = ARCHS[name](f)
    good_binned = [c for c in f.binned if in_range(f.volts(c))]
    return f, verdict, good_binned


def kind(verdict):
    """Short label for a verdict, for the sweep table."""
    pairs = (("accepted", "accepted"), ("total", "total"),
             ("a cell", "bad cell"), ("cells,", "short"),
             ("stopped", "stopped"), ("not fin", "timeout"))
    for key, label in pairs:
        if key in verdict:
            return label
    return "other"


def sweep(a):
    labels = ["accepted", "total", "bad cell", "short", "stopped"]
    seeds = range(a.seed, a.seed + a.sweep)
    mal = "on" if a.malfunction else "off"
    print(f"seeds {seeds[0]} to {seeds[-1]}, malfunction {mal}")
    print(f"{'':13s}" + "".join(f"{x:>9s}" for x in labels)
          + "  binned")
    for name in ARCHS:
        count, binned = dict.fromkeys(labels + ["timeout"], 0), 0
        for s in seeds:
            a2 = argparse.Namespace(**{**vars(a), "seed": s})
            f, verdict, good_binned = run(name, a2)
            count[kind(verdict)] += 1
            binned += len(good_binned)
        row = "".join(f"{count[x]:9d}" for x in labels)
        print(f"{name:13s}{row}{binned:8d}")


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--arch", choices=list(ARCHS), default=None)
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--cells", type=int, default=10)
    p.add_argument("--pick-fail", type=float, default=0.2)
    p.add_argument("--retries", type=int, default=2)
    p.add_argument("--no-malfunction", dest="malfunction",
                   action="store_false")
    p.add_argument("--tester", type=int, default=1)
    p.add_argument("--start", type=float, default=20.0)
    p.add_argument("--duration", type=float, default=45.0)
    p.add_argument("--limit", type=float, default=300.0)
    p.add_argument("--sweep", type=int, default=0)
    a = p.parse_args()

    if a.sweep:
        sweep(a)
        return
    names = [a.arch] if a.arch else list(ARCHS)
    if a.arch is None:
        f = Factory(a)
        print("cells (true V):",
              " ".join(f"{v:.2f}" for v in f.v))
    for name in names:
        f, verdict, good_binned = run(name, a)
        if a.arch:                       # the trace, then the verdict
            f.note(verdict)
            print("\n".join(f.log))
            continue
        print(f"{name}, done at {f.t:.0f} s:")
        print(f"  {verdict}")
        if good_binned:
            cells = ", ".join(map(str, good_binned))
            print(f"  in-range cells recycled: {cells}")


if __name__ == "__main__":
    main()
