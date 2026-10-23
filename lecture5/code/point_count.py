"""How many lidar points land on one cell? (SYNTHETIC geometry)

A lidar 0.1 m from the cell axis, at the cell's mid-height, faces a
good cell. Count the rays of one scan that hit the cell, for three
scan layouts of 400 samples each. Then count the points of a whole
pass on the belt, from two lidars (box A and box B).
"""
import numpy as np
import synth as S

LAYOUTS = {   # name: ((H, min, max), (V, min, max))
    "docs example": ((50, -1.57, 1.57), (8, -0.5, 0.5)),
    "narrow 20x20": ((20, -0.15, 0.15), (20, -0.4, 0.4)),
    "narrow 10x40": ((10, -0.15, 0.15), (40, -0.4, 0.4)),
}
rng = np.random.default_rng(0)
x = 0.65
t_mid = (x - S.SPAWN_X) / S.SPEED      # cell axis right in front
print("one scan, cell axis 0.1 m in front of the lidar")
for name, (h, v) in LAYOUTS.items():
    lidar = S.two_lidars(x, h, v)[0]
    local = S.scan(lidar, t_mid, [], rng)
    pts = S.to_world(lidar, local[np.isfinite(local[:, 0])])
    on_cell = pts[:, 2] > S.BELT_Z + 0.001
    step_h = (h[2] - h[1]) / (h[0] - 1)
    step_v = (v[2] - v[1]) / (v[0] - 1)
    print(f"  {name}: steps {step_h:.3f} and {step_v:.3f} rad, "
          f"{on_cell.sum()} of {h[0] * v[0]} rays hit the cell")
print("whole pass, belt at 0.1 m/s, 20 Hz, t in s after spawn")
PASSES = {
    "two lidars, 20x20": S.two_lidars(x, *LAYOUTS["narrow 20x20"]),
    "two lidars, 10x40": S.two_lidars(x, *LAYOUTS["narrow 10x40"]),
    "four lidars, 10x40": S.four_lidars(),
}
for name, lidars in PASSES.items():
    pts, times = S.pass_cell(lidars, [], rng, 0.0)
    seen = times[pts[:, 2] > S.BELT_Z + 0.001]
    print(f"  {name}: {len(seen)} points, seen at t = "
          f"{seen.min():.2f} to {seen.max():.2f}")
