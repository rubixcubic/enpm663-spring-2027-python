"""Averaging noisy voltage readings (SYNTHETIC readings).

The noise is normal with a standard deviation of 0.05 V, the value in
ARIAC's voltage_tester/model.sdf (<noise_std_dev>). The true voltage,
3.78 V, is chosen for this example: inside the Li-Ion range of 3.4 V
to 3.8 V (CellTypes.msg: 3.6 V plus or minus 0.2 V).
"""
import numpy as np

SIGMA, TRUE_V, HIGH = 0.05, 3.78, 3.8
OPERATIONAL, MALFUNCTIONING = 1, 2      # OperationStates.msg
rng = np.random.default_rng(3)

# Part 1: how often does a reading, or an average, cross 3.8 V?
trials = 100_000
one = TRUE_V + rng.normal(0, SIGMA, trials)
ten = TRUE_V + rng.normal(0, SIGMA, (trials, 10)).mean(axis=1)
print(f"{trials} trials, true voltage {TRUE_V} V")
print(f"  one reading above {HIGH} V:     {np.mean(one > HIGH):.3f}")
print(f"  average of 10 above {HIGH} V:   {np.mean(ten > HIGH):.3f}")
print(f"  spread of the average of 10: {ten.std():.4f} V")

# Part 2: a stream from one tester; skip readings that are not valid
stream = [(0.0 + rng.normal(0, SIGMA), OPERATIONAL)   # no cell yet
          for _ in range(2)]
stream += [(TRUE_V + rng.normal(0, SIGMA), OPERATIONAL)
           for _ in range(6)]
stream += [(-1.0, MALFUNCTIONING)] * 3
stream += [(TRUE_V + rng.normal(0, SIGMA), OPERATIONAL)
           for _ in range(6)]
valid = [v for v, status in stream
         if status == OPERATIONAL and v > 1.0]
print(f"stream: {len(stream)} messages, {len(valid)} valid")
for i in range(0, len(stream), 9):
    print("  " + " ".join(f"{v:5.2f}" for v, _ in stream[i:i + 9]))
mean = np.mean(valid[-10:])
print(f"  average of the last 10 valid: {mean:.3f} V -> "
      f"{'in range' if 3.4 <= mean <= 3.8 else 'out of range'}")
