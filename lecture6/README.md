# Lecture 6 scripts

Eight managed scripts, plus two PDDL domains and three PDDL problems. None of
them uses ROS 2 or the ARIAC simulation: the planner works on PDDL files, and
the factory state is a Python dictionary with values chosen for the
examples.

A managed file is one that `tools/sync_course.py` keeps identical here and in
the course's slides and docs repositories (the slides repository only, for a
file the docs do not carry).

- **`plan_kit.py`**: Demo 1: load the domain and problem, plan, print the
  plan, write `../outputs/plan.txt`. Slide: "lecture6/code/plan_kit.py
  (lines 11 to 23)". Writes `outputs/plan_kit.txt` and `outputs/plan.txt`.
- **`validate_plan.py`**: Demo 2: validate `plan.txt` and a copy with steps 6
  and 7 swapped. Slide: "lecture6/code/validate_plan.py (lines 14 to 29)".
  Writes `outputs/validate_plan.txt` and `outputs/plan_swapped.txt`.
- **`gen_problem.py`**: Demo 3: write a problem from a stand-in factory
  state, then plan. Also defines `make_problem()`. Slide:
  "lecture6/code/gen_problem.py (lines 9 to 18)". Writes
  `outputs/problem_generated.pddl` and `outputs/gen_problem.txt`.
- **`compare_planners.py`**: Demo 4: satisficing against optimal, on 4 cells
  and on 8 cells. Slide: "Output: lecture6/outputs/compare_planners.txt".
  Writes `outputs/compare_planners.txt` and `outputs/problem_large.pddl`.
- **`mistakes.py`**: Demo 5: two modeling mistakes and the plans they
  produce. Slide: "Output: lecture6/outputs/mistakes.txt". Writes
  `outputs/mistakes.txt`.
- **`select_cells.py`**: Demo 6: the kit voltage window and the selection
  step, without and with look-ahead. Slide: "lecture6/code/select_cells.py
  (lines 15 to 25)". Writes `outputs/select_cells.txt`.
- **`numeric_try.py`**: Demo 7: give Fast Downward the kit window as numeric
  PDDL. Slide: "Output: lecture6/outputs/numeric_try.txt (from
  numeric_try.py)". Writes `outputs/numeric_try.txt`.
- **`kit_margin.py`**: Demo 8: how far the look-ahead kit sits from ARIAC's
  limits, and how often ARIAC's check would reject it. Slide: "Output:
  lecture6/outputs/kit_margin.txt (from kit_margin.py)". Writes
  `outputs/kit_margin.txt`.
