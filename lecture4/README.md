# Lecture 4 scripts

Five managed scripts. They use `py_trees` alone and tick a tree of stand-in
leaves: no robot, no ROS 2 node and no simulator.

- **`composite_status.py`**: the status a sequence, a selector and three
  decorators return from their children's statuses. Slide:
  "lecture4/code/composite_status.py (excerpt)". Writes
  `outputs/composite_status.txt`.
- **`parallel_watch.py`**: a parallel that watches the tester while it waits
  for five readings, with `synchronise` True and False. Slide:
  "lecture4/code/parallel_watch.py (output)". Writes
  `outputs/parallel_watch.txt`.
- **`retry_demo.py`**: a `Retry` around a pick that fails once, in a sequence
  with memory and without memory. Slide: "lecture4/code/retry_demo.py
  (excerpt)". Writes `outputs/retry_demo.txt`.
- **`blackboard_demo.py`**: blackboard keys for three cells, and a reader
  that tries to write. Slide: "lecture4/code/blackboard_demo.py (excerpt)".
  Writes `outputs/blackboard_demo.txt`.
- **`kit_spread.py`**: how far the sum of four averaged voltages wanders, by
  formula and in 100,000 simulated kits. Not shown on a slide. Writes
  `outputs/kit_spread.txt`.
