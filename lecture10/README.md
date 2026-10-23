# Lecture 10 scripts

Two managed scripts, out of five in the lecture; the other three
(`tf_agv_moves.py`, `tf_failures.py`, `pixel_to_table.py`) use ROS 2 and are
not here.

A managed file is one that `tools/sync_course.py` keeps identical here and in
the course's slides and docs repositories (the slides repository only, for a
file the docs do not carry).

- **`conveyor_intercept.py`**: when the course skill catches a cell on the
  moving conveyor, and when it refuses, in four separate runs. Not shown on
  a slide. Writes `outputs/conveyor_intercept.txt`.
- **`rrt_connect_toy.py`**: RRT-Connect for a point in a flat square: five
  seeds, five paths. Slide: "The Class Demonstration
  (lecture10/code/rrt_connect_toy.py)". Writes `outputs/rrt_connect.txt` and
  `outputs/rrt_seed1.json`.
