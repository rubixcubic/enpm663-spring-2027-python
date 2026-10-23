"""What a 20-run batch with a bar of 19 of 20 can show.

The course skills package tests a skill in batches of 20 runs, and the
skill passes at 19 of 20 or better (README, "Measured success counts").
A skill whose true success rate is p passes when all 20 runs succeed,
or when exactly 1 of the 20 fails. The failed run can be any of the
20, so

    P(pass) = p^20 + 20 x p^19 x (1 - p)

The true rates below are chosen for this example. A simulation with a
fixed seed checks the formula.
"""
import numpy as np

N, BAR = 20, 19
REPEATS = 1_000_000
rng = np.random.default_rng(seed=19)

print(f"A batch of {N} runs passes at {BAR} of {N} or better")
for p in [0.80, 0.90, 0.95, 0.99]:
    all_pass = p ** N
    one_fail = N * p ** (N - 1) * (1 - p)
    sim = np.mean(rng.binomial(N, p, size=REPEATS) >= BAR)
    print(f"  p = {p:.2f}: {all_pass:.3f} + {one_fail:.3f} = "
          f"{all_pass + one_fail:.2f} (simulated {sim:.2f})")
