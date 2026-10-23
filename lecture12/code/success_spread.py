"""How much a success rate measured over n runs moves by chance.

A system that completes the trial with true probability P_TRUE (chosen
for this example) is tested n times, and the test is repeated REPEATS
times for each n. The seed is fixed, so every run of this program
prints the same numbers.

Part 2: two systems with the SAME true rate, 20 runs each. How often
does chance alone make them look 0.10 or more apart?

Writes a text report to stdout and the ranges to
../outputs/success_spread.json (read by the figure).
"""
import json
import math
import pathlib

import numpy as np

P_TRUE = 0.80
RUNS = [5, 10, 20, 50, 100]
REPEATS = 10_000
rng = np.random.default_rng(seed=12)

print(f"True success rate {P_TRUE:.2f}, {REPEATS} repeats per n")
rows = []
for n in RUNS:
    rates = rng.binomial(n, P_TRUE, size=REPEATS) / n
    lo, hi = np.percentile(rates, [2.5, 97.5])
    se = math.sqrt(P_TRUE * (1 - P_TRUE) / n)
    print(f"  n = {n:3d}: middle 95% {lo:.2f} to {hi:.2f}, "
          f"spread {rates.std():.3f}, formula {se:.3f}")
    rows.append({"n": n, "lo": lo, "hi": hi, "se": se,
                 "first": rates[:40].tolist()})

n = 20
a = rng.binomial(n, P_TRUE, size=REPEATS) / n
b = rng.binomial(n, P_TRUE, size=REPEATS) / n
gap = np.abs(a - b)
print(f"Two equal systems, {n} runs each:")
print(f"  gap of 0.10 or more: {np.mean(gap >= 0.10 - 1e-9):.1%}")
two_se = 2 * math.sqrt(2 * P_TRUE * (1 - P_TRUE) / n)
print(f"  gap above 2 SE ({two_se:.3f}): {np.mean(gap > two_se):.1%}")

out = pathlib.Path(__file__).parent.parent / "outputs"
(out / "success_spread.json").write_text(
    json.dumps({"p_true": P_TRUE, "rows": rows}) + "\n")
