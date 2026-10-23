"""How far chance moves a kit total built from averaged tester readings.

ENPM663 L4, Pattern 3. The tree adds four averaged voltages; ARIAC checks
the cells' true voltages. The ARIAC 2025 tester adds Gaussian noise with a
standard deviation of 0.05 V to each reading
(ariac_gz/models/voltage_tester/model.sdf, noise_std_dev). Each average
here uses the five readings that wait_for_voltage collects.

Part 1 is the formula: an average of n readings wanders by about
sigma / sqrt(n), and a sum of four independent averages by sqrt(4) times
that. Part 2 checks it: 100,000 kits whose true total sits exactly on the
window's upper edge, 14.55 V, read the way the tree reads them.
"""
import math
import random

SIGMA = 0.05             # V, per reading (model.sdf)
TOTAL_READ = 14.62       # V, the kit total the averages give (L4 slide)
EDGE = 14.55             # V, top of the kit window (4 x 3.6 + 0.15)
TRUE_CELLS = [3.55, 3.62, 3.70, 3.68]   # true voltages that total 14.55 V
KITS = 100_000


def tail(z):
    """P(Z >= z) for a standard normal Z."""
    return 0.5 * math.erfc(z / math.sqrt(2))


def simulate(n, rng):
    """Fraction of kits whose sum of averages reads TOTAL_READ or more."""
    sums = []
    for _ in range(KITS):
        s = 0.0
        for v in TRUE_CELLS:
            s += sum(v + rng.gauss(0.0, SIGMA) for _ in range(n)) / n
        sums.append(s)
    mean = sum(sums) / KITS
    sd = math.sqrt(sum((x - mean) ** 2 for x in sums) / (KITS - 1))
    over = sum(1 for x in sums if x >= TOTAL_READ - 1e-12) / KITS
    return sd, over


def main():
    rng = random.Random(663)
    print(f"true cells {TRUE_CELLS} total {sum(TRUE_CELLS):.2f} V; "
          f"reading noise {SIGMA} V")
    for n in (5, 20):
        s_avg = SIGMA / math.sqrt(n)
        s_sum = math.sqrt(4) * s_avg
        z = (TOTAL_READ - EDGE) / s_sum
        sd, over = simulate(n, rng)
        print(f"{n} readings per cell")
        print(f"  formula: one average {s_avg:.4f} V, sum of four "
              f"{s_sum:.4f} V")
        print(f"  {TOTAL_READ} V is {TOTAL_READ - EDGE:.2f} V over "
              f"{EDGE} V: {z:.2f} spreads; P = {100 * tail(z):.1f}%")
        print(f"  simulated {KITS} kits at {EDGE} V: spread {sd:.4f} V, "
              f"{100 * over:.1f}% read {TOTAL_READ} V or more")


if __name__ == "__main__":
    main()
