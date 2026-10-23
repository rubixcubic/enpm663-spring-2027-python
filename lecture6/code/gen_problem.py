"""L6 demo 3: write a PDDL problem from the factory state, then plan.

STATE is a stand-in for what a team's node reads from ARIAC and its
own records; the values are chosen for this example.
"""
from unified_planning.io import PDDLReader
from unified_planning.shortcuts import OneshotPlanner, get_environment

LOW, HIGH = 3.4, 3.8                  # Li-Ion 3.6 V +/- 0.2 V

STATE = {
    "agv_station": {"agv1": "inspection"},   # /agv1/info
    "free_slots": {"agv1": ["s1", "s2", "s3", "s4"]},  # tray
    "on_tester": {"tester2": "c5"},          # team records
    "voltage": {"c5": 3.86},                 # averaged readings
    "at_door": ["c1", "c2", "c3", "c4"],     # passed inspection
    "kit": {"agv1": ["c1", "c2", "c3", "c4"]},  # selection step
}


def make_problem(state):
    cells = state["at_door"] + list(state["on_tester"].values())
    testers = ["tester1", "tester2"]
    init = ["(picks-conveyor inspection_robot_1)",
            "(loads-agv inspection_robot_2)",
            "(hand-free inspection_robot_1)",
            "(hand-free inspection_robot_2)"]
    init += [f"(serves {r} {t})" for t in testers
             for r in ("inspection_robot_1", "inspection_robot_2")]
    for t in testers:
        c = state["on_tester"].get(t)
        init.append(f"(on-tester {c} {t})" if c
                    else f"(tester-free {t})")
    for agv, station in state["agv_station"].items():
        init.append(f"(agv-at {agv} {station})")
        init += [f"(slot-free {agv} {s})"
                 for s in state["free_slots"][agv]]
    init += [f"(at-door {c})" for c in state["at_door"]]
    goal = []
    for c in cells:
        v = state["voltage"].get(c)
        if v is None or LOW <= v <= HIGH:   # untested: assume ok
            init.append(f"(voltage-ok {c})")
        else:
            init.append(f"(voltage-bad {c})")
            goal.append(f"(recycled {c})")
    for agv, kit in state["kit"].items():
        goal += [f"(in-slot {c} {agv} s{i})"
                 for i, c in enumerate(kit, start=1)]
        goal.append(f"(submitted {agv})")
    agvs = " ".join(state["agv_station"])
    return "\n".join([
        "(define (problem generated) (:domain task1)",
        f"  (:objects {' '.join(cells)} - cell",
        "    inspection_robot_1 inspection_robot_2 - robot",
        f"    {' '.join(testers)} - tester {agvs} - agv)",
        "  (:init", *("    " + f for f in init), "  )",
        "  (:goal (and", *("    " + g for g in goal), "  )))"])


if __name__ == "__main__":
    text = make_problem(STATE)
    with open("../outputs/problem_generated.pddl", "w") as f:
        f.write(text + "\n")

    get_environment().credits_stream = None
    problem = PDDLReader().parse_problem(
        "domain.pddl", "../outputs/problem_generated.pddl")
    with OneshotPlanner(name="fast-downward") as planner:
        result = planner.solve(problem)
    print("status:", result.status.name)
    for step, action in enumerate(result.plan.actions, start=1):
        print(f"{step:2d}. {action}")
