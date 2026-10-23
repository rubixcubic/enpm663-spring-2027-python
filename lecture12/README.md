# Lecture 12 scripts

Four managed scripts. None of them uses ROS 2 or the ARIAC simulation: they
read small data files that sit next to them, or need none, and print their
results.

A managed file is one that `tools/sync_course.py` keeps identical here and in
the course's slides and docs repositories (the slides repository only, for a
file the docs do not carry).

- **`perception_metrics.py`**: precision and recall from a labeled set of 20
  cells, and the position error of 8 top shell spawns. Slide:
  "lecture12/code/perception_metrics.py (excerpt)". Writes
  `outputs/perception.txt`.
- **`success_spread.py`**: how far chance moves a success rate measured over
  n runs. Slide: "lecture12/code/success_spread.py (excerpt)". Writes
  `outputs/success_spread.txt` and `outputs/success_spread.json`.
- **`batch_bar.py`**: how often a 20-run batch passes a bar of 19 of 20, for
  four true success rates. Not shown on a slide. Writes
  `outputs/batch_bar.txt`.
- **`score_calculator.py`**: the ARIAC 2025 run score of the two
  worked-example runs, computed the way `scoring.py` does. Slide:
  "lecture12/code/score_calculator.py (excerpt)". Writes
  `outputs/score_runs.txt` and `outputs/score_runs.json`.
