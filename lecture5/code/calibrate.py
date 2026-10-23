"""Step 6: set the threshold from good cells (SYNTHETIC data).

Twenty good cells pass the lidars. For each, the detector's residual
d is measured, and the threshold is the largest |d| seen, rounded up
to the next 0.1 mm. Range noise of 0.2 mm is chosen for this example:
ARIAC's lidar model.sdf sets no noise element.
"""
import numpy as np
import synth as S
import detector as D

NOISE = 0.0002          # m, chosen for this example
rng = np.random.default_rng(5)
thresholds = []
for name, lidars in (("two lidars", S.two_lidars()),
                     ("four lidars", S.four_lidars())):
    worst = []
    for _ in range(20):
        pts, times = S.pass_cell(lidars, [], rng, NOISE)
        d = D.detect(pts, times, S.SPEED, threshold=1.0)["d"]
        worst.append(np.abs(d).max() * 1000)
    threshold = np.ceil(max(worst) * 10) / 10
    thresholds.append(threshold)
    print(f"{name}: 20 good cells, {len(d)} points per cell")
    print(f"  largest |d| per cell: {min(worst):.2f} to "
          f"{max(worst):.2f} mm, threshold {threshold:.1f} mm")
print(f"used for both layouts: {max(thresholds):.1f} mm, the larger of "
      f"the two")
