"""Precision, recall and position error from a small labeled set.

cells.csv: 20 cells. "defective" is the ground truth (in simulation,
from ARIAC's log_cell_info:=true log); "flagged" is the detector's
answer. shell_poses.csv: 8 top shell spawns, true and estimated
position in meters, in a frame on the assembly table. Every value in
both files is chosen for this example.
"""
import csv
import math
import pathlib
import statistics

HERE = pathlib.Path(__file__).parent


def read(name):
    with open(HERE / name, newline="") as fh:
        return list(csv.DictReader(fh))


cells = read("cells.csv")
tp = fp = fn = tn = 0
for c in cells:
    truth, flag = c["defective"] == "1", c["flagged"] == "1"
    if truth and flag:
        tp += 1
    elif flag:
        fp += 1
    elif truth:
        fn += 1
    else:
        tn += 1

print(f"{len(cells)} cells: TP {tp}, FP {fp}, FN {fn}, TN {tn}")
print(f"precision = {tp}/{tp + fp} = {tp / (tp + fp):.2f}")
print(f"recall    = {tp}/{tp + fn} = {tp / (tp + fn):.2f}")

errors = []
for s in read("shell_poses.csv"):
    dx = float(s["est_x"]) - float(s["true_x"])
    dy = float(s["est_y"]) - float(s["true_y"])
    errors.append(1000 * math.hypot(dx, dy))  # millimeters
print("position error (mm):", " ".join(f"{e:.1f}" for e in errors))
print(f"mean {statistics.mean(errors):.1f} mm, "
      f"spread (sample SD) {statistics.stdev(errors):.1f} mm, "
      f"largest {max(errors):.1f} mm")
