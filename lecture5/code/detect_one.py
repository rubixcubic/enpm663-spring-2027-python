"""One SYNTHETIC cell with a dent, a scratch and a bulge.

Each defect is 2 mm deep at its deepest point (the Scenario page's
minimum). Sizes and places are chosen for this example. The detector
runs steps 1 to 8 and prints what it finds next to the truth.
"""
import sys
import numpy as np
import synth as S
import detector as D

THRESHOLD = 0.0009      # m, from outputs/calibrate.txt
NOISE = 0.0002          # m, chosen for this example
TRUTH = [
    S.defect(S.DENT, -1.0, 0.018, 0.002, 0.004),
    S.defect(S.SCRATCH, 1.3, 0.038, 0.002, 0.004, 0.028),
    S.defect(S.BULGE, -2.3, 0.050, 0.002, 0.004),
]
rng = np.random.default_rng(7)
pts, times = S.pass_cell(S.two_lidars(), TRUTH, rng, NOISE)
r = D.detect(pts, times, S.SPEED, THRESHOLD)
print(f"1 crop:     {r['raw']} points in, {r['cropped']} kept")
print("2 separate: one cell on the belt in this run")
print("3 motion:   points moved back to the first scan's time")
print(f"4 fit:      axis x0 = {r['x0']:.4f} m, y0 = {r['y0']:.4f} m,"
      f" radius {r['r_fit'] * 1000:.2f} mm")
print(f"5 residual: d from {r['d'].min() * 1000:.2f} to "
      f"{r['d'].max() * 1000:.2f} mm")
print(f"6 flag:     {r['flagged']} points with |d| > "
      f"{THRESHOLD * 1000:.1f} mm")
print(f"7, 8:       {len(r['defects'])} clusters")
print("found                         truth")
for kind, th, z, n in sorted(r["defects"], key=lambda f: f[2]):
    t = min(TRUTH, key=lambda d: abs(d["z"] - z))
    dth = np.angle(np.exp(1j * (th - t["theta"])))
    ok = (kind == t["type"] and abs(z - t["z"]) <= 0.005
          and abs(dth) <= 0.26)
    print(f"{S.NAMES[kind]:7s} th {th:+.2f} z {z * 1000:4.1f} mm "
          f"({n:2d} pts) | {S.NAMES[t['type']]:7s} th "
          f"{t['theta']:+.2f} z {t['z'] * 1000:4.1f} mm  "
          f"{'match' if ok else 'NO MATCH'}")
seen = times[(pts[:, 2] > S.BELT_Z + 0.002)]
print(f"last scan that sees the cell: t = {seen.max():.2f} s "
      f"after spawn")
if len(sys.argv) > 1:          # write the residual map for a figure
    p = r["points"]
    th = np.arctan2(p[:, 1] - r["y0"], p[:, 0] - r["x0"])
    np.savetxt(sys.argv[1], np.column_stack(
        [th, (p[:, 2] - S.BELT_Z) * 1000, r["d"] * 1000]),
        fmt="%.5f", delimiter=",", header="theta,z_mm,d_mm")
