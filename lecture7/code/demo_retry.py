"""L7 demo 2: Retry around a pick that fails, with mock skills.

Usage: demo_retry.py FAILURES
The mock skill answers GRASP_FAILED the first FAILURES times, then
succeeds. Retry allows num_failures=3. Values chosen for this demo.
"""
import sys

import executor as ex
from executor import ROBOT

PLAN = [
    f"(pick-from-tester {ROBOT} c3 tester1)",
    f"(place-in-slot {ROBOT} c3 agv1 s3)",
]
START = [
    ("serves", ROBOT, "tester1"), ("hand-free", ROBOT),
    ("on-tester", "c3", "tester1"), ("voltage-ok", "c3"),
    ("slot-free", "agv1", "s3"), ("agv-at", "agv1", "inspection"),
]

ex.set_facts(START)
factory = ex.MockFactory({1: "c3", 2: None}, {1: [], 2: []},
                         {"c3": 3.62})
factory.inject["pick_from_tester"] = int(sys.argv[1])
ex.RETRIES["pick-from-tester"] = 3  # Retry(..., num_failures=3)
root = ex.build_tree(PLAN, factory)
status, ticks = ex.run(root)
print(f"plan {status.name} after {ticks} ticks; "
      f"{factory.goals} goals sent")
