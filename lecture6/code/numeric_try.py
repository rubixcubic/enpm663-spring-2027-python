"""L6 demo 7: give Fast Downward the kit window as numeric PDDL."""
import warnings

from unified_planning.io import PDDLReader
from unified_planning.shortcuts import OneshotPlanner, get_environment

get_environment().credits_stream = None

problem = PDDLReader().parse_problem(
    "kit_numeric.pddl", "kit_numeric_problem.pddl")
print("needs numeric planning:",
      problem.kind.has_general_numeric_planning())
with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter("always")
    with OneshotPlanner(name="fast-downward") as planner:
        result = planner.solve(problem)
for warning in caught:
    print("warning:", warning.message)
print("status:", result.status.name)
print("plan:", result.plan)
KEEP = ("Reason", "translate exit code")
for message in result.log_messages:
    for line in message.message.splitlines():
        if line.startswith(KEEP):
            print("log:", line)
