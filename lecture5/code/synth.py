"""SYNTHETIC lidar scans of an ARIAC battery cell (ENPM663 L5).

Nothing here comes from a simulation. The cell, its defects, the
lidars and the noise are made up in NumPy. Values taken from the
ARIAC 2025 source (branch ariac2025) are marked with their file.
"""
import numpy as np

# battery_cell/model.sdf, collision cylinder:
# radius 0.0105, length 0.07
R = 0.0105
LENGTH = 0.07
# cell_feed_plugin.hpp: battery_spawn_location = {0.55, 1, 0.422}
SPAWN_X, BELT_Y, BELT_Z = 0.55, 1.0, 0.422
# inspection_conveyor/model.sdf: belt 1 m by 0.1 m, model at y = 1
BELT_HALF_WIDTH = 0.05
# lidar/model.sdf: <range> min 0.04, max 0.2
RANGE_MIN, RANGE_MAX = 0.04, 0.2
# Chosen for this example (CONVEYOR_SPEED may be at most 0.1 m/s)
SPEED = 0.1
DENT, BULGE, SCRATCH = 1, 2, 3   # CellDefect.msg
NAMES = {DENT: "dent", BULGE: "bulge", SCRATCH: "scratch"}


class Lidar:
    """A lidar at (x, y, z), turned by yaw about z (no tilt)."""

    def __init__(self, name, xyz, yaw, h, v, rate=20):
        self.name, self.xyz, self.yaw = name, np.array(xyz), yaw
        self.rate = rate
        az = np.linspace(h[1], h[2], h[0])   # h = (samples, min, max)
        el = np.linspace(v[1], v[2], v[0])
        az, el = np.meshgrid(az, el)
        self.az, self.el = az.ravel(), el.ravel()

    def rays_local(self):
        """Unit ray directions in the lidar's own frame."""
        c = np.cos(self.el)
        return np.stack([c * np.cos(self.az), c * np.sin(self.az),
                         np.sin(self.el)], axis=1)

    def rotation(self):
        c, s = np.cos(self.yaw), np.sin(self.yaw)
        return np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])


def defect(kind, theta, z, depth, size, length=None):
    """A defect: theta (rad, world), z (m from the cell base).

    depth is how far the deepest point is from the surface (m).
    size is the radius of a dent or bulge, or a scratch's width.
    length is a scratch's length along the cell axis.
    """
    return {"type": kind, "theta": theta, "z": z, "depth": depth,
            "size": size, "length": length}


def surface_offset(theta, z, defects):
    """Radial offset (m) of the surface from R at (theta, z)."""
    out = np.zeros_like(theta)
    for d in defects:
        dt = np.angle(np.exp(1j * (theta - d["theta"])))
        u, v = R * dt, z - d["z"]          # along the arc, along z
        if d["type"] == SCRATCH:
            half = d["size"] / 2
            inside = (np.abs(u) < half) & \
                (np.abs(v) < d["length"] / 2)
            groove = d["depth"] * (1 - (u / half) ** 2)
            out -= np.where(inside, groove, 0)
        else:
            s2 = (u ** 2 + v ** 2) / d["size"] ** 2
            sign = 1.0 if d["type"] == BULGE else -1.0
            out += np.where(s2 < 1, sign * d["depth"] * (1 - s2), 0)
    return out


def cast(origin, dirs, axis_xy, defects):
    """Distance along each ray to the cell side or the belt.
    A ray that hits neither gives inf."""
    t_out = np.full(len(dirs), np.inf)
    # Cell side: bisection between the entry into a cylinder 4 mm
    # larger than the cell and the closest approach to the axis.
    o = origin[:2] - axis_xy
    dxy = dirs[:, :2]
    a = np.sum(dxy ** 2, axis=1)
    b = 2 * dxy @ o
    c = o @ o - (R + 0.004) ** 2
    disc = b ** 2 - 4 * a * c
    ok = disc > 0
    t0 = np.where(ok, (-b - np.sqrt(np.abs(disc))) / (2 * a), np.inf)
    t1 = np.where(ok, -b / (2 * a), np.inf)

    def f(t):
        p = origin + t[:, None] * dirs
        rel = p[:, :2] - axis_xy
        th = np.arctan2(rel[:, 1], rel[:, 0])
        rho = np.hypot(rel[:, 0], rel[:, 1])
        return rho - R - surface_offset(th, p[:, 2] - BELT_Z, defects)

    ok &= (t0 > 0) & (f(np.where(ok, t1, 0.0)) < 0)
    lo, hi = np.where(ok, t0, 0.0), np.where(ok, t1, 0.0)
    for _ in range(40):
        mid = (lo + hi) / 2
        outside = f(mid) > 0
        lo = np.where(outside, mid, lo)
        hi = np.where(outside, hi, mid)
    z_hit = origin[2] + hi * dirs[:, 2] - BELT_Z
    ok &= (z_hit >= 0) & (z_hit <= LENGTH)
    t_out[ok] = hi[ok]
    # Belt surface: the plane z = BELT_Z, inside the belt's width.
    down = dirs[:, 2] < 0
    dz = np.where(down, dirs[:, 2], -1.0)
    tb = np.where(down, (BELT_Z - origin[2]) / dz, np.inf)
    yb = origin[1] + tb * dirs[:, 1]
    tb = np.where(np.abs(yb - BELT_Y) <= BELT_HALF_WIDTH, tb, np.inf)
    t_out = np.minimum(t_out, tb)
    t_out[(t_out < RANGE_MIN) | (t_out > RANGE_MAX)] = np.inf
    return t_out


def scan(lidar, t, defects, rng, noise=0.0):
    """One scan at time t (s after spawn). Returns lidar-frame points,
    one row per ray; a ray that hits nothing gives a row of inf."""
    axis_xy = np.array([SPAWN_X + SPEED * t, BELT_Y])
    local = lidar.rays_local()
    world_dirs = local @ lidar.rotation().T
    rng_m = cast(lidar.xyz, world_dirs, axis_xy, defects)
    hit = np.isfinite(rng_m)
    rng_m[hit] += rng.normal(0.0, noise, hit.sum())
    return local * rng_m[:, None]


def to_world(lidar, pts):
    """Lidar frame to world frame (what a TF2 lookup would give)."""
    return pts @ lidar.rotation().T + lidar.xyz


def two_lidars(x=0.65, h=(10, -0.15, 0.15), v=(40, -0.4, 0.4)):
    """Box A and box B lidars facing the belt, 0.1 m from the cell
    axis, at the cell's mid-height. Positions chosen for this example
    (box A: y 0.7 to 0.95, box B: y 1.05 to 1.3, z 0.42 to 0.62)."""
    zc = BELT_Z + LENGTH / 2
    a = Lidar("lidar_a", (x, BELT_Y - 0.1, zc), np.pi / 2, h, v)
    b = Lidar("lidar_b", (x, BELT_Y + 0.1, zc), -np.pi / 2, h, v)
    return [a, b]


def four_lidars(x=0.7, turn=0.6, h=(10, -0.15, 0.15),
                v=(40, -0.4, 0.4)):
    """Two lidars in box A and two in box B, at x = 0.7 m (two_lidars()
    uses 0.65 m), each pair turned 0.6 rad upstream and downstream so
    that the front and back of the cell are seen (chosen for this
    example)."""
    zc = BELT_Z + LENGTH / 2
    out = []
    for side, y, yaw in (("a", BELT_Y - 0.1, np.pi / 2),
                         ("b", BELT_Y + 0.1, -np.pi / 2)):
        for k, sign in ((1, 1), (2, -1)):
            turn_k = sign * turn if side == "a" else -sign * turn
            out.append(Lidar(f"lidar_{side}{k}", (x, y, zc),
                             yaw + turn_k, h, v))
    return out


def pass_cell(lidars, defects, rng, noise, t_start=0.0,
              t_end=3.0):
    """All scans of one cell passing the lidars. Returns world points
    and the time of the scan each point came from."""
    pts, times = [], []
    for lidar in lidars:
        n = int(round((t_end - t_start) * lidar.rate)) + 1
        for t in t_start + np.arange(n) / lidar.rate:
            local = scan(lidar, t, defects, rng, noise)
            keep = np.all(np.isfinite(local), axis=1)
            pts.append(to_world(lidar, local[keep]))
            times.append(np.full(keep.sum(), t))
    return np.vstack(pts), np.concatenate(times)


def random_defect(rng, depth_range):
    """One defect with a random type, place and depth."""
    kind = rng.choice([DENT, BULGE, SCRATCH])
    theta = rng.uniform(-np.pi, np.pi)
    depth = rng.uniform(*depth_range)
    if kind == SCRATCH:
        return defect(kind, theta, rng.uniform(0.02, 0.05), depth,
                      0.004, 0.028)
    return defect(kind, theta, rng.uniform(0.01, 0.06), depth, 0.004)
