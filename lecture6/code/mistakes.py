"""L6 demo 5: two modeling mistakes and the plans they produce.

Each mistake deletes one piece of domain.pddl, in memory, and plans
problem.pddl with the changed domain. The file itself is unchanged.
The script prints the plan steps that show the mistake.
"""
from unified_planning.io import PDDLReader
from unified_planning.shortcuts import OneshotPlanner, get_environment

get_environment().credits_stream = None

DOMAIN = open("domain.pddl").read()
PROBLEM = open("problem.pddl").read()

MISTAKES = {   # name: (text to find, replacement, steps to print)
    "submit-kit without (kit-checked ?a)": (
        "(and (kit-checked ?a) (agv-at ?a shipping))",
        "(agv-at ?a shipping)", range(1, 4)),
    "pick-from-conveyor without (not (hand-free ?r))": (
        "(holding ?r ?c) (not (hand-free ?r))",
        "(holding ?r ?c)", range(4, 7)),
}

for name, (old, new, steps) in MISTAKES.items():
    assert DOMAIN.count(old) == 1, name
    domain = DOMAIN.replace(old, new)
    problem = PDDLReader().parse_problem_string(domain, PROBLEM)
    with OneshotPlanner(name="fast-downward") as planner:
        plan = planner.solve(problem).plan
    print(f"{name}: {len(plan.actions)} steps")
    for step in steps:
        print(f"{step:2d}. {plan.actions[step - 1]}")
