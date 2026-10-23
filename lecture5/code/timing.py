"""How long does it take to move one scan to the world frame?

400 SYNTHETIC points (one scan of 400 samples) are moved by the 4 x 4
matrix m of pc2_roundtrip.py, three ways:
  loop A: one NumPy product per point (m @ [x, y, z, 1])
  loop B: plain Python floats, no NumPy inside the loop
  all at once: one NumPy product for every point, as on the slide
Each way runs 200 times; the best of 3 such runs gives the time per
scan. The whole measurement is repeated 5 times, because the times
change from run to run. They also depend on the PC: the output names
it.
"""
import platform
import timeit
import numpy as np
import synth as S

lidar = S.two_lidars()[0]
c, s = np.cos(lidar.yaw), np.sin(lidar.yaw)
m = np.eye(4)
m[:3, :3] = [[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]]
m[:3, 3] = lidar.xyz
xyz = np.random.default_rng(0).uniform(-0.1, 0.1, (400, 3))
rows = m.tolist()
pts = xyz.tolist()


def loop_numpy():
    return np.array([(m @ [x, y, z, 1.0])[:3] for x, y, z in pts])


def loop_python():
    return [[r[0] * x + r[1] * y + r[2] * z + r[3] for r in rows[:3]]
            for x, y, z in pts]


def all_at_once():
    return (np.c_[xyz, np.ones(len(xyz))] @ m.T)[:, :3]


assert np.allclose(loop_numpy(), all_at_once())
assert np.allclose(loop_python(), all_at_once())
cpu = next((ln.split(":", 1)[1].strip()
            for ln in open("/proc/cpuinfo") if ln.startswith("model name")),
           platform.processor())
print(f"PC: {cpu}; Python {platform.python_version()}, "
      f"NumPy {np.__version__}")
print("400 points, best of 3 x 200 runs, ms per scan, 5 repeats")
WAYS = (("loop A, NumPy per point", loop_numpy),
        ("loop B, plain Python", loop_python),
        ("all at once, NumPy", all_at_once))
for name, f in WAYS:
    ms = [min(timeit.repeat(f, number=200, repeat=3)) / 200 * 1000
          for _ in range(5)]
    print(f"  {name:24s} " + " ".join(f"{t:6.3f}" for t in ms))
