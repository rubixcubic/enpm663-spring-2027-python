"""A simple cylinder-fit defect detector (ENPM663 L5).

Input: world points from the lidars of one cell, and the time of the
scan each point came from. The steps follow the lecture's pipeline.
"""
import numpy as np

R = 0.0105            # battery_cell/model.sdf
BELT_Y, BELT_Z = 1.0, 0.422
DENT, BULGE, SCRATCH = 1, 2, 3


def crop(pts):
    """Step 1: keep points over the belt, 2 mm to 66 mm above it."""
    h = pts[:, 2] - BELT_Z
    keep = (np.abs(pts[:, 1] - BELT_Y) < 0.05) & (h > 0.002) \
        & (h < 0.066)
    return keep


def undo_motion(pts, times, speed):
    """Step 3: move every point back to where the cell was at the
    first scan, t0."""
    out = pts.copy()
    out[:, 0] -= speed * (times - times.min())
    return out


def fit_circle(x, y):
    """Step 4: least-squares circle through (x, y)."""
    a = np.column_stack([x, y, np.ones_like(x)])
    sol = np.linalg.lstsq(a, x ** 2 + y ** 2, rcond=None)[0]
    x0, y0 = sol[0] / 2, sol[1] / 2
    return x0, y0, np.sqrt(sol[2] + x0 ** 2 + y0 ** 2)


def residuals(pts, x0, y0):
    """Step 5: distance from the axis minus R (negative: inset)."""
    return np.hypot(pts[:, 0] - x0, pts[:, 1] - y0) - R


def clusters(p, gap=0.003, min_points=3):
    """Step 7: group flagged points closer than gap to each other."""
    label = -np.ones(len(p), dtype=int)
    groups = []
    for i in range(len(p)):
        if label[i] >= 0:
            continue
        label[i], todo, members = len(groups), [i], [i]
        while todo:
            j = todo.pop()
            near = np.where((label < 0) & (np.linalg.norm(
                p - p[j], axis=1) < gap))[0]
            label[near] = len(groups)
            todo.extend(near)
            members.extend(near)
        groups.append(np.array(members))
    return [g for g in groups if len(g) >= min_points]


def classify(p, d, x0, y0):
    """Step 8: type from the sign and shape; theta and z from the
    centroid of the cluster."""
    th = np.arctan2(p[:, 1] - y0, p[:, 0] - x0)
    mean = np.angle(np.mean(np.exp(1j * th)))
    u = R * np.angle(np.exp(1j * (th - mean)))   # along the arc
    z = p[:, 2] - BELT_Z                          # along the axis
    if np.mean(d) > 0:
        kind = BULGE
    else:
        ev = np.linalg.eigvalsh(np.cov(np.vstack([u, z])))
        long_ = np.sqrt(ev[1] / max(ev[0], 1e-12)) > 2.5
        kind = SCRATCH if long_ else DENT
    return kind, mean, float(np.mean(z))


def detect(pts, times, speed, threshold):
    """Run steps 1 to 8. Returns a dict with every stage's result."""
    keep = crop(pts)
    p = undo_motion(pts[keep], times[keep], speed)
    x0, y0, r_fit = fit_circle(p[:, 0], p[:, 1])
    d = residuals(p, x0, y0)
    # Refit on the points that look normal, so a defect does not
    # pull the axis toward itself.
    ok = np.abs(d) <= threshold
    x0, y0, r_fit = fit_circle(p[ok, 0], p[ok, 1])
    d = residuals(p, x0, y0)
    flagged = np.abs(d) > threshold
    found = []
    for sign in (1, -1):           # never mix inset and outset points
        idx = np.where(flagged & (np.sign(d) == sign))[0]
        for g in clusters(p[idx]):
            k = idx[g]
            found.append(classify(p[k], d[k], x0, y0) + (len(k),))
    return {"raw": len(pts), "cropped": int(keep.sum()), "x0": x0,
            "y0": y0, "r_fit": r_fit, "d": d, "points": p,
            "flagged": int(flagged.sum()), "defects": found}
