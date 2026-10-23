# Lecture 2 scripts

One managed script, the toy factory. It runs one short Task 1 run under
three architectures (plan only, react only, three layers) while a voltage
tester malfunctions.

- **`toy_factory.py`**: the toy factory and its three architectures. Slide:
  "lecture2/code/toy_factory.py (excerpt)". Writes `outputs/summary.txt`,
  `outputs/plan_only.txt`, `outputs/react_only.txt`,
  `outputs/three_layers.txt`, `outputs/no_malfunction.txt`,
  `outputs/sweep.txt` and `outputs/sweep_off.txt` (one file per mode the
  script runs in).
