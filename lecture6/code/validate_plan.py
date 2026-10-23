"""L6 demo 2: validate the plan from plan_kit.py, then an edited copy.

The edited copy swaps steps 6 and 7, so inspection_robot_2 places
c1 in slot s1 before it picks c1 from the tester.
"""
from unified_planning.io import PDDLReader
from unified_planning.shortcuts import PlanValidator, get_environment

get_environment().credits_stream = None

reader = PDDLReader()
problem = reader.parse_problem("domain.pddl", "problem.pddl")

lines = open("../outputs/plan.txt").read().splitlines()
lines[5], lines[6] = lines[6], lines[5]          # steps 6 and 7
with open("../outputs/plan_swapped.txt", "w") as f:
    f.write("\n".join(lines) + "\n")

with PlanValidator(problem_kind=problem.kind) as validator:
    print("validator:", validator.name)
    for name in ["plan.txt", "plan_swapped.txt"]:
        plan = reader.parse_plan(problem, "../outputs/" + name)
        result = validator.validate(problem, plan)
        print(f"{name}: {result.status.name}")
        if result.reason is not None:
            print("  reason:", result.reason.name)
            print("  failed step:", result.inapplicable_action)
            for message in result.log_messages:
                print("  log:", message.message)
