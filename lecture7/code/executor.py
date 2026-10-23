"""L7: a plan-to-BT executor with mock skills (no ROS, no simulator).

MockFactory stands in for ARIAC and the course skills package. The
executor sees it only through skill results and the tray status, as
a GP3 executor sees ARIAC. The blackboard holds the executor's own
view of the world as a set of PDDL facts, written as tuples.
"""
import py_trees
from py_trees.common import Access, Status

ROBOT = "inspection_robot_2"
LOG = print  # every trace line goes through here


def fact_text(fact):
    return "(" + " ".join(fact) + ")"


class MockFactory:
    """What is really true. Values are chosen for each demo."""

    def __init__(self, testers, queues, volts):
        self.tester = dict(testers)  # tester number -> cell
        self.queue = {t: list(q) for t, q in queues.items()}
        self.volts = dict(volts)  # true voltage of each cell
        self.tray = {}  # (agv, slot) -> cell
        self.held = None
        self.station = {1: 1}  # agv -> station_id
        self.inject = {}  # skill -> failures still to inject
        self.goals = 0  # goals sent to the mock skills
        self.on_new_cell = None  # called when a cell lands

    def result(self, skill, ok):
        if self.inject.get(skill, 0) > 0:
            self.inject[skill] -= 1
            return "GRASP_FAILED"
        return "SUCCESS" if ok else "PRECONDITION_FAILED"

    def refill(self, t):
        # Stand-in for inspection_robot_1: the next cell for
        # tester t lands on it as soon as the tester is free.
        cell = self.queue[t].pop(0) if self.queue[t] else None
        self.tester[t] = cell
        if cell and self.on_new_cell:
            self.on_new_cell(cell, t)

    # The skills (course skills package) and the AGV action.
    def pick_from_tester(self, t):
        ok = self.held is None and self.tester[t] is not None
        code = self.result("pick_from_tester", ok)
        if code == "SUCCESS":
            self.held = self.tester[t]
            self.refill(t)
        return code

    def place_in_slot(self, agv, slot):
        ok = self.held and (agv, slot) not in self.tray
        code = self.result("place_in_slot", ok)
        if code == "SUCCESS":
            self.tray[(agv, slot)] = self.held
            self.held = None
        return code

    def drop_in_recycling(self):
        code = self.result("drop_in_recycling", bool(self.held))
        if code == "SUCCESS":
            self.held = None
        return code

    def move(self, agv, station_id):  # ARIAC's /agvN/move
        self.station[agv] = station_id
        return "SUCCESS"

    def read_average(self, t):  # 10 readings at 10 Hz, averaged
        return self.volts[self.tester[t]]

    def slot_occupied(self, agv, slot):  # /agvN/tray_status
        return (agv, slot) in self.tray


class Guard(py_trees.behaviour.Behaviour):
    """Checks that every precondition is a fact on the blackboard."""

    def __init__(self, name, needs):
        super().__init__(name)
        self.needs = needs
        self.bb = self.attach_blackboard_client()
        self.bb.register_key("facts", access=Access.READ)

    def update(self):
        for fact in self.needs:
            if fact not in self.bb.facts:
                self.feedback_message = fact_text(fact) + " is false"
                return Status.FAILURE
        return Status.SUCCESS


class Act(py_trees.behaviour.Behaviour):
    """Sends one goal, returns RUNNING until the result arrives."""

    def __init__(self, name, factory, skill, goal, ticks=2):
        super().__init__(name)
        self.factory, self.skill, self.goal = factory, skill, goal
        self.ticks = ticks
        self.value = None

    def initialise(self):
        self.left = self.ticks
        self.factory.goals += 1

    def update(self):
        self.left -= 1
        if self.left > 0:
            return Status.RUNNING
        if self.skill == "read_average":
            self.value = self.factory.read_average(*self.goal)
            self.feedback_message = f"average {self.value:.2f} V"
            return Status.SUCCESS
        code = getattr(self.factory, self.skill)(*self.goal)
        self.feedback_message = code
        return Status.SUCCESS if code == "SUCCESS" else Status.FAILURE


class Verify(py_trees.behaviour.Behaviour):
    """Checks that the effect happened in the factory."""

    def __init__(self, name, check, what):
        super().__init__(name)
        self.check, self.what = check, what

    def update(self):
        if self.check():
            return Status.SUCCESS
        self.feedback_message = "expected " + self.what
        return Status.FAILURE


class Update(py_trees.behaviour.Behaviour):
    """Writes the action's effects to the blackboard."""

    def __init__(self, name, add, delete):
        super().__init__(name)
        self.add, self.delete = add, delete
        self.bb = self.attach_blackboard_client()
        self.bb.register_key("facts", access=Access.WRITE)

    def update(self):
        kept = self.bb.facts - set(self.delete)
        self.bb.facts = kept | set(self.add)
        return Status.SUCCESS


def subtree(label, needs, act, verify, add, delete):
    """One plan step: guard, act, verify, update."""
    return py_trees.composites.Sequence(label, memory=True, children=[
        Guard("guard", needs), act, verify,
        Update("update", add, delete)])


def number(name):  # agv1 -> 1, s3 -> 3, tester2 -> 2
    return int(name.lstrip("agvstester"))


STATION_ID = {"inspection": 1, "assembly": 2,  # AgvStations.msg
              "shipping": 3, "recycling": 4}


def build_pick_from_tester(f, label, r, c, t):
    needs = [("serves", r, t), ("on-tester", c, t), ("hand-free", r)]
    goal = (number(t),)
    return subtree(
        label, needs,
        Act("act", f, "pick_from_tester", goal),
        Verify("verify", lambda: f.held == c, f"holding {c}"),
        add=[("holding", r, c)],
        delete=[("on-tester", c, t), ("hand-free", r)])


def build_place_in_slot(f, label, r, c, a, s):
    needs = [("holding", r, c), ("voltage-ok", c),
             ("slot-free", a, s), ("agv-at", a, "inspection")]
    goal = (number(a), number(s))  # agv1 s3 -> agv 1, slot 3
    return subtree(
        label, needs,
        Act("act", f, "place_in_slot", goal),
        Verify("verify", lambda: f.slot_occupied(*goal),
               f"{s} occupied"),
        add=[("in-slot", c, a, s), ("hand-free", r)],
        delete=[("holding", r, c), ("slot-free", a, s)])


class ReadAverage(Act):
    """Act leaf of check-voltage. The average is an observation, so
    it goes on the blackboard at once, before the verify step."""

    def __init__(self, name, factory, cell, tester):
        super().__init__(name, factory, "read_average", (tester,),
                         ticks=10)
        self.cell = cell
        self.bb = self.attach_blackboard_client()
        self.bb.register_key("volts", access=Access.WRITE)

    def update(self):
        status = super().update()
        if status == Status.SUCCESS:
            self.bb.volts = {**self.bb.volts, self.cell: self.value}
        return status


def build_check_voltage(f, label, c, t):
    act = ReadAverage("act", f, c, number(t))
    return subtree(
        label, [("on-tester", c, t)], act,
        Verify("verify", lambda: 3.4 <= act.value <= 3.8,
               f"{c} in 3.4 V to 3.8 V"),
        add=[("voltage-ok", c)], delete=[])


def build_recycle(f, label, r, c):
    return subtree(
        label, [("holding", r, c)],
        Act("act", f, "drop_in_recycling", ()),
        Verify("verify", lambda: f.held is None, "hand empty"),
        add=[("hand-free", r)], delete=[("holding", r, c)])


def build_move_agv(f, label, a, frm, to):
    goal = (number(a), STATION_ID[to])  # shipping -> station_id 3
    return subtree(
        label, [("agv-at", a, frm)],
        Act("act", f, "move", goal, ticks=3),
        Verify("verify", lambda: f.station[goal[0]] == goal[1],
               f"{a} at {to}"),
        add=[("agv-at", a, to)], delete=[("agv-at", a, frm)])


REGISTRY = {
    "pick-from-tester": build_pick_from_tester,
    "place-in-slot": build_place_in_slot,
    "check-voltage": build_check_voltage,
    "recycle": build_recycle,
    "move-agv": build_move_agv,
}
RETRIES = {}  # action name -> num_failures; empty: no Retry


def build_tree(plan, factory):
    """The plan-to-BT factory: one subtree per plan action."""
    steps = []
    for i, action in enumerate(plan, start=1):
        name, *args = action.strip("()").split()
        if name not in REGISTRY:
            raise KeyError(f"step {i}: no builder for {name}")
        step = REGISTRY[name](factory, f"{i} {name}", *args)
        if name in RETRIES:
            step = py_trees.decorators.Retry(
                f"retry {i}", step, num_failures=RETRIES[name])
        steps.append(step)
    return py_trees.composites.Sequence(
        "plan", memory=True, children=steps)


def why(node):
    """The feedback of the leaf that ended a failed step."""
    for leaf in node.iterate():
        if leaf.status == Status.FAILURE and leaf.feedback_message:
            return f"{leaf.name}: {leaf.feedback_message}"
    return ""


def run(root, max_ticks=200, running=True):
    """Ticks the tree; logs each step's status change."""
    watch = []
    for step in root.children:  # a Retry: watch it and its child
        watch += [getattr(step, "decorated", None), step]
    watch = [node for node in watch if node is not None]
    last = {}
    for tick in range(1, max_ticks + 1):
        root.tick_once()
        for step in watch:
            if step.status != last.get(step.name):
                last[step.name] = step.status
                quiet = step.status == Status.INVALID or (
                    step.status == Status.RUNNING and not running)
                if not quiet:
                    LOG(f"tick {tick:>2}: {step.name} "
                        f"{step.status.name}")
                if step.status == Status.FAILURE:
                    LOG(f"tick {tick:>2}:   {why(step)}")
        if root.status != Status.RUNNING:
            return root.status, tick
    return root.status, max_ticks


def set_facts(facts, volts=None):
    """Puts the starting facts on the blackboard."""
    py_trees.blackboard.Blackboard.set("/facts", set(facts))
    py_trees.blackboard.Blackboard.set("/volts", dict(volts or {}))


def get_facts():
    return py_trees.blackboard.Blackboard.get("/facts")


def get_volts():
    return py_trees.blackboard.Blackboard.get("/volts")
