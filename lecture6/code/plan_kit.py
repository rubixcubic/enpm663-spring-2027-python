"""L6 demo 1: load domain.pddl and problem.pddl, plan, print the plan.

Run with the venv that has unified-planning and up-fast-downward.
Writes the plan to ../outputs/plan.txt for validate_plan.py.
"""
from unified_planning.io import PDDLReader, PDDLWriter
from unified_planning.shortcuts import OneshotPlanner, get_environment

get_environment().credits_stream = None  # no engine banner

problem = PDDLReader().parse_problem("domain.pddl", "problem.pddl")
print(f"{len(problem.actions)} actions, "
      f"{len(problem.all_objects)} objects, "
      f"{len(problem.goals[0].args)} goal facts")

with OneshotPlanner(name="fast-downward") as planner:
    result = planner.solve(problem)

print("status:", result.status.name)
for step, action in enumerate(result.plan.actions, start=1):
    print(f"{step:2d}. {action}")

PDDLWriter(problem).write_plan(result.plan, "../outputs/plan.txt")
