"""A factory without ARIAC, for the L8 and L9 exercises and tests (orchestrator.py --fake).

Same tool names, arguments and result shapes as skill_tools.SkillTools. Every value
here is chosen for this example: the cells' voltages, 20 simulation seconds per
skill, and the tester malfunction windows."""
from typing import Literal

from skill_tools import DECLARATIONS

SKILL_SECONDS = 20.0   # simulation seconds per skill call, chosen for this example
ACT_TOOLS = [d["name"] for d in DECLARATIONS if d["name"].startswith("robot")]   # the robot skills


class FakeTools:
    def __init__(self, cell_volts=(3.61, 3.55, 3.66, 3.58), tester_down=None, fail_once=None):
        self.t = 0.0
        self.volts = list(cell_volts)            # each fed cell's voltage, in feed order
        self.holding = {"robot1": None, "robot2": None}   # None, or the held cell's voltage
        self.on_tester = {1: None, 2: None}
        self.tray = {a: [False] * 4 for a in (1, 2, 3)}
        self.tester_down = dict(tester_down or {})       # tester: (start, end) in simulation s
        self.fail_once = dict(fail_once or {})           # tool name: code, returned once
        other = sorted(set(self.fail_once) - set(ACT_TOOLS))
        if other:
            raise ValueError(f"fail_once takes robot skill names only ({', '.join(ACT_TOOLS)}), "
                             f"not {', '.join(other)}")
        self.calls = []

    def declarations(self, names=None):
        return [d for d in DECLARATIONS if names is None or d["name"] in names]

    def call(self, name, args):
        self.calls.append((name, dict(args)))
        if name in self.fail_once:
            robot = name.split("_")[0]
            return self._result(robot, self.fail_once.pop(name), "failure chosen for this example")
        if name.startswith("robot"):
            self.t += SKILL_SECONDS
        return getattr(self, name)(**args)

    def snapshot(self):
        return {"sim_time_s": self.t, "testers": self.read_testers(), "conveyor": self.read_conveyor(),
                "agvs": {str(a): self.read_agv(a) for a in (1, 2, 3)}}

    def _result(self, robot, code="SUCCESS", message=""):
        held = "CELL" if self.holding[robot] is not None else "NOTHING"
        return {"code": code, "holding": held, "message": message, "attempts": 1,
                "wall_s": 0.0}   # chosen: the fake moves no robot, so it takes no wall time

    def _down(self, n):
        start, end = self.tester_down.get(n, (0.0, 0.0))
        return start <= self.t < end

    def robot1_move_home(self) -> dict:
        return self._result("robot1", message="parked")

    def robot1_pick_from_conveyor(self) -> dict:
        if self.holding["robot1"] is not None or not self.volts:
            return self._result("robot1", "PRECONDITION_FAILED", "robot 1 holds a cell, or no cells left")
        self.holding["robot1"] = self.volts.pop(0)
        return self._result("robot1")

    def robot1_place_on_tester(self, tester: Literal[1, 2]) -> dict:
        if self.holding["robot1"] is None:
            return self._result("robot1", "PRECONDITION_FAILED", "robot 1 holds nothing")
        self.on_tester[tester], self.holding["robot1"] = self.holding["robot1"], None
        return self._result("robot1")

    def robot2_move_home(self) -> dict:
        return self._result("robot2", message="parked")

    def robot2_pick_from_tester(self, tester: Literal[1, 2]) -> dict:
        if self.on_tester[tester] is None:
            return self._result("robot2", "GRASP_FAILED", "nothing on the tester")
        self.holding["robot2"], self.on_tester[tester] = self.on_tester[tester], None
        return self._result("robot2")

    def robot2_place_in_slot(self, agv: Literal[1, 2, 3], slot: Literal[1, 2, 3, 4]) -> dict:
        if self.holding["robot2"] is None:
            return self._result("robot2", "PRECONDITION_FAILED", "robot 2 holds nothing")
        self.tray[agv][slot - 1], self.holding["robot2"] = True, None
        return self._result("robot2")

    def robot2_drop_in_recycling(self) -> dict:
        self.holding["robot2"] = None
        return self._result("robot2")

    def read_testers(self) -> dict:
        return {str(n): ({"voltage": -1.0, "status": "MALFUNCTIONING"} if self._down(n)
                         else {"voltage": self.on_tester[n] or 0.0, "status": "OPERATIONAL"})
                for n in (1, 2)}

    def read_conveyor(self) -> dict:
        return {"status": "OPERATIONAL", "speed": 0.1}

    def read_agv(self, agv: Literal[1, 2, 3]) -> dict:
        return {"station": "INSPECTION", "slots": {str(k): self.tray[agv][k - 1] for k in (1, 2, 3, 4)}}

    def wait(self, seconds: int) -> dict:
        self.t += seconds
        return {"waited_sim_s": float(seconds)}
