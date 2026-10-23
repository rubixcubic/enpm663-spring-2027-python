"""Precision and recall over a set of SYNTHETIC cells.

200 cells pass the lidars. Each cell is defective with probability
0.25 and then has one defect of a random type, place and depth (all
chosen for this example). A cell is rejected when the detector finds
any defect. The same cells are scored for two lidar layouts.

For each missed defect, the script prints its angle (rad) and depth (mm)
to 2 decimals, so a depth near the 0.9 mm threshold shows on which side
it falls. It also counts the points that landed on the defect, how many
of those pass the threshold (a cluster needs 3), and the deepest d seen
on it (mm, in the defect's direction: inward for a dent or scratch).
"""
import numpy as np
import synth as S
import detector as D

NOISE = 0.0002
LAYOUTS = {"two lidars": S.two_lidars(),
           "four lidars": S.four_lidars()}


def make_truths(rng, n, depth_range):
    return [[S.random_defect(rng, depth_range)]
            if rng.random() < 0.25 else [] for _ in range(n)]


def score(truths, lidars, threshold, rng):
    tp = fp = fn = tn = classified = 0
    missed = []
    for truth in truths:
        pts, times = S.pass_cell(lidars, truth, rng, NOISE)
        r = D.detect(pts, times, S.SPEED, threshold)
        found = r["defects"]
        if truth and found:
            tp += 1
            t, (kind, th, z, _) = truth[0], found[0]
            dth = np.angle(np.exp(1j * (th - t["theta"])))
            classified += (len(found) == 1 and kind == t["type"]
                           and abs(z - t["z"]) <= 0.005
                           and abs(dth) <= 0.26)
        elif truth:
            fn += 1
            missed.append((truth[0], r))
        elif found:
            fp += 1
        else:
            tn += 1
    prec = tp / (tp + fp) if tp + fp else float("nan")
    print(f"  {threshold * 1000:.1f} mm: TP {tp:2d} FP {fp:2d} "
          f"FN {fn:2d} TN {tn:3d}  precision {prec:.2f} "
          f"recall {tp / (tp + fn):.2f}")
    print(f"          classified (ARIAC rule) {classified} of "
          f"{tp + fn}")
    return missed


def print_missed(missed, threshold):
    """One line per missed defect: what landed on it, and how deep."""
    if not missed:
        return
    print(f"    missed   theta  depth  points  above {threshold * 1000:.1f}"
          f"  deepest")
    for t, r in missed:
        p, d = r["points"], r["d"]
        th = np.arctan2(p[:, 1] - r["y0"], p[:, 0] - r["x0"])
        on_it = S.surface_offset(th, p[:, 2] - S.BELT_Z, [t]) != 0
        inward = 1.0 if t["type"] == S.BULGE else -1.0
        dd = inward * d[on_it]
        deepest = f"{dd.max() * 1000:7.2f}" if len(dd) else "      -"
        print(f"    {S.NAMES[t['type']]:7s}  {t['theta']:+.2f}  "
              f"{t['depth'] * 1000:5.2f}  {on_it.sum():6d}  "
              f"{np.sum(dd > threshold):9d}  {deepest}")


rng = np.random.default_rng(11)
truths = make_truths(rng, 200, (0.002, 0.003))
bad = sum(1 for t in truths if t)
print(f"set 1: 200 cells, {bad} defective, depth 2 to 3 mm")
print(" two lidars")
for thr in (0.0005, 0.0009, 0.0015):
    missed = score(truths, LAYOUTS["two lidars"], thr, rng)
    if thr == 0.0009:
        print_missed(missed, thr)
print(" four lidars")
score(truths, LAYOUTS["four lidars"], 0.0009, rng)
truths = make_truths(rng, 200, (0.0008, 0.0025))
bad = sum(1 for t in truths if t)
print(f"set 2: 200 cells, {bad} defective, depth 0.8 to 2.5 mm")
print(" four lidars")
missed = score(truths, LAYOUTS["four lidars"], 0.0009, rng)
print_missed(missed, 0.0009)
