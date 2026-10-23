# Lecture 5 scripts

Nine managed scripts. Two are modules the others import (`synth.py`,
`detector.py`); the rest print the outputs the slides show.

A managed file is one that `tools/sync_course.py` keeps identical here and in
the course's slides and docs repositories (the slides repository only, for a
file the docs do not carry).

- **`synth.py`**: module, not a script; synthetic scans of a cell, its
  defects and the lidars. Slide: "Made Up in NumPy (lecture5/code/synth.py)".
  No output file of its own; imported by the other scripts.
- **`detector.py`**: module, not a script; the cylinder-fit detector, a
  function for each coded step. Slide: "lecture5/code/detector.py
  (excerpt)". No output file of its own; imported by the other scripts.
- **`point_count.py`**: counts the rays that hit a cell, for one scan and for
  a whole pass. Slide: "lecture5/code/point_count.py: Output". Writes
  `outputs/point_count.txt`.
- **`calibrate.py`**: sets the threshold from 20 good cells. Slide: "Step 6
  on 20 Good Cells (lecture5/code/calibrate.py)". Writes
  `outputs/calibrate.txt`.
- **`detect_one.py`**: runs the detector on one cell with a dent, a scratch
  and a bulge. Slide: "lecture5/code/detect_one.py: Output". Writes
  `outputs/detect_one.txt` and `outputs/residuals.csv`.
- **`precision_recall.py`**: scores the detector on 200 cells, for two
  layouts and three thresholds. Slide: "lecture5/code/precision_recall.py:
  Output (Part 1)". Writes `outputs/precision_recall.txt`.
- **`voltage_average.py`**: averages noisy voltage readings and skips
  invalid ones. Slide: "lecture5/code/voltage_average.py (excerpt)". Writes
  `outputs/voltage_average.txt`.
- **`timing.py`**: times moving one scan to the world frame: two loops and
  one NumPy product. Not shown on a slide. Writes `outputs/timing.txt`
  (listed in `tools/noise.txt`: the measured times change from run to run and
  from PC to PC).
- **`mesh_depths.py`**: measures the depth of ARIAC's training defects from
  the meshes. Slide: "lecture5/code/mesh_depths.py: Output". Writes
  `outputs/mesh_depths.txt`; needs the environment variable `ARIAC_SRC` set
  to an ARIAC 2025 source checkout, which this repository does not have, so
  `run_repo.sh` skips this step here.
