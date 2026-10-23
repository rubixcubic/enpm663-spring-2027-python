"""L6 demo 4: a satisficing and an optimal planner on two problems.

Small: problem.pddl (4 cells, 1 AGV). Large: 8 cells and 2 AGVs,
written by make_problem() from a stand-in state chosen for this
example. Times are wall-clock seconds for one run on this PC.
"""
import time

from unified_planning.io import PDDLReader
from unified_planning.model.metrics import (
    MinimizeSequentialPlanLength)
from unified_planning.shortcuts import OneshotPlanner, get_environment

from gen_problem import make_problem

get_environment().credits_stream = None

cells = [f"c{i}" for i in range(1, 9)]
LARGE = {
    "agv_station": {"agv1": "inspection", "agv2": "inspection"},
    "free_slots": {"agv1": ["s1", "s2", "s3", "s4"],
                   "agv2": ["s1", "s2", "s3", "s4"]},
    "on_tester": {}, "voltage": {}, "at_door": cells,
    "kit": {"agv1": cells[:4], "agv2": cells[4:]},
}
with open("../outputs/problem_large.pddl", "w") as f:
    f.write(make_problem(LARGE) + "\n")

reader = PDDLReader()
for label, path in [("4 cells", "problem.pddl"),
                    ("8 cells", "../outputs/problem_large.pddl")]:
    problem = reader.parse_problem("domain.pddl", path)
    problem.add_quality_metric(MinimizeSequentialPlanLength())
    for engine in ["fast-downward", "fast-downward-opt"]:
        with OneshotPlanner(name=engine) as planner:
            start = time.perf_counter()
            result = planner.solve(problem, timeout=120)
            seconds = time.perf_counter() - start
        steps = len(result.plan.actions) if result.plan else "-"
        print(f"{label}  {engine:18s} {result.status.name:18s} "
              f"steps {steps:>3}  {seconds:6.2f} s")
