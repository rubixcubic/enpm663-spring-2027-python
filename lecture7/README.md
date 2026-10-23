# Lecture 7 scripts

Seven managed scripts. None of them uses ROS communication or the ARIAC
simulation: the skills, the testers and the AGV are mock stand-ins written in
Python.

- **`executor.py`**: the plan-to-BT executor: the mock factory, the guard,
  act, verify and update leaves, the builders, the registry, `build_tree`
  and the tick logger. The demos import it; it is not run on its own. Slide:
  "lecture7/code/executor.py (excerpt)". No output file of its own.
- **`demo_factory.py`**: Demo 1: a five-step plan becomes a tree, and two
  bugs (no memory, no guards). Slide: "Output of demo_factory.py build".
  Writes `outputs/factory_build.txt`, `outputs/factory_tick.txt`,
  `outputs/factory_trace.txt`, `outputs/factory_unknown.txt`,
  `outputs/factory_nomemory.txt` and `outputs/factory_noguard.txt`.
- **`demo_retry.py`**: Demo 2: Retry around a pick that fails. Slide: "Output
  of demo_retry.py 2 (the Mock Pick Fails Twice, Then Succeeds)". Writes
  `outputs/retry_2.txt` and `outputs/retry_3.txt`.
- **`demo_timeout.py`**: Demo 3: Timeout around a leaf that waits for valid
  voltage readings. Slide: "lecture7/code/demo_timeout.py (excerpt)". Writes
  `outputs/timeout_normal.txt`, `outputs/timeout_silent.txt` and
  `outputs/timeout_malfunction.txt`.
- **`demo_nesting.py`**: Demo 4: `Retry(Timeout(act))` against
  `Timeout(Retry(act))`. Slide: "Output of demo_nesting.py hang (the Act
  Never Finishes)". Writes `outputs/nesting_hang.txt` and
  `outputs/nesting_fail.txt`.
- **`demo_replan.py`**: Demo 5: the replanning loop on a cell with a bad
  voltage. Slide: "Output of demo_replan.py (Part 1 of 5)". Writes
  `outputs/replan.txt`.
- **`demo_place_cell.py`**: the same tree as the BehaviorTree.CPP example, in
  `py_trees`. Slide: "lecture7/code/demo_place_cell.py (excerpt)". Writes
  `outputs/pytrees_1.txt` and `outputs/pytrees_3.txt`.
