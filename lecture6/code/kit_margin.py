"""L6 demo 8: the look-ahead kit from select_cells.py, against chance.

The four voltages are averages of 10 tester readings. ARIAC's tester
adds normal noise with a standard deviation (sd) of 0.05 V to each
reading (ariac_gz/models/voltage_tester/model.sdf, noise_std_dev), so
an average of 10 readings has an sd of 0.05 / sqrt(10) V, and the sum
of four averages has twice that. ARIAC's kit check uses the true
voltages: each cell within 0.2 V of 3.6 V, the total within 0.15 V of
14.4 V (agv_tray_interface_plugin.cpp, check_kit_quality).

Model 1 (the slide): each true voltage is its average plus a normal
error with that sd, independent from cell to cell.
Model 2: also uses how ARIAC makes the cells. Its cell feed draws each
true voltage from a normal distribution around 3.6 V with an sd of
0.1 V (ariac_plugins cell_feed_plugin.hpp, voltage_std_dev), which
pulls a high reading's likely true voltage back toward 3.6 V.

Both models draw DRAWS kits of true voltages and count how many fail
ARIAC's check. The seed is fixed, so the output repeats exactly.
"""
import math
import random

NOMINAL, CELL_TOL, KIT_TOL = 3.6, 0.2, 0.15
KIT = [("c1", 3.75), ("c2", 3.78), ("c5", 3.45), ("c6", 3.52)]
SD = 0.05 / math.sqrt(10)          # one average of 10 readings
SD_KIT = SD * math.sqrt(len(KIT))  # the sum of four averages
SPREAD = 0.1                       # ARIAC's spread of true voltages
DRAWS = 1_000_000


def rejected(means, sd, seed):
    """Fraction of simulated kits that ARIAC's check rejects."""
    rng = random.Random(seed)
    bad = 0
    for _ in range(DRAWS):
        true = [rng.gauss(m, sd) for m in means]
        if (any(abs(v - NOMINAL) > CELL_TOL for v in true)
                or abs(sum(true) - 4 * NOMINAL) > KIT_TOL):
            bad += 1
    return bad / DRAWS


low, high = NOMINAL - CELL_TOL, NOMINAL + CELL_TOL
print(f"sd of one average: 0.05 / sqrt(10) = {SD:.3f} V")
print(f"sd of the kit total: {SD:.3f} x 2 = {SD_KIT:.3f} V")
for cell, v in KIT:
    if high - v <= v - low:
        gap, side = high - v, f"below {high:.1f} V"
    else:
        gap, side = v - low, f"above {low:.1f} V"
    print(f"{cell} {v:.2f} V: {gap:.2f} V {side} = {gap / SD:.1f} sd")
total = round(sum(v for _, v in KIT), 2)
kit_high = 4 * NOMINAL + KIT_TOL
gap = kit_high - total
print(f"kit {total:.2f} V: {gap:.2f} V below {kit_high:.2f} V "
      f"= {gap / SD_KIT:.1f} sd")
share = rejected([v for _, v in KIT], SD, seed=1)
print(f"model 1: ARIAC rejects {100 * share:.1f} % of {DRAWS} kits")
w = SPREAD ** -2 / (SPREAD ** -2 + SD ** -2)
post = [w * NOMINAL + (1 - w) * v for _, v in KIT]
post_sd = (SPREAD ** -2 + SD ** -2) ** -0.5
share = rejected(post, post_sd, seed=2)
print(f"model 2: ARIAC rejects {100 * share:.1f} % of {DRAWS} kits")
