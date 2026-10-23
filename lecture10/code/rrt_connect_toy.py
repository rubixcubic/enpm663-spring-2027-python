"""A teaching toy: RRT-Connect for a point in a flat 10 m square.

Not MoveIt and not OMPL. It shows what a sampling-based planner does:
two trees, one from the start and one from the goal, grow toward
random samples until they meet. MoveIt's OMPL planners sample the same
way, in the arm's joint space (six joint angles for a UR arm).
The walls, the start, the goal and the step are chosen for this
example. Algorithm: Kuffner and LaValle, ICRA 2000.
Writes ../outputs/rrt_seed1.json (trees and path) for the figure.
"""

import json
import sys

import numpy as np

WALLS = [(3.0, 0.0, 4.0, 7.0), (6.0, 3.0, 7.0, 10.0)]  # x0 y0 x1 y1
# The shortest route: a taut string from the start, around the wall
# corners (3, 7), (4, 7), (6, 3), (7, 3), to the goal.
CORNERS = [(1.5, 1.5), (3, 7), (4, 7), (6, 3), (7, 3), (8.5, 8.5)]
START, GOAL = np.array([1.5, 1.5]), np.array([8.5, 8.5])
STEP, SIZE, MAX_ITER = 0.5, 10.0, 5000


def free(p, q):
    """True if segment p-q touches no wall (checked every 5 cm)."""
    n = max(2, int(np.linalg.norm(q - p) / 0.05) + 1)
    for s in np.linspace(0.0, 1.0, n):
        x, y = p + s * (q - p)
        for x0, y0, x1, y1 in WALLS:
            if x0 <= x <= x1 and y0 <= y <= y1:
                return False
    return True


def extend(tree, target):
    """One step from the nearest node toward target."""
    pts = np.array([node for node, _ in tree])
    i = int(np.argmin(np.linalg.norm(pts - target, axis=1)))
    near = pts[i]
    gap = np.linalg.norm(target - near)
    if gap <= STEP:
        new = target
    else:
        new = near + STEP * (target - near) / gap
    if not free(near, new):
        return "trapped"
    tree.append((new, i))
    return "reached" if gap <= STEP else "advanced"


def connect(tree, target):
    """Repeat extend toward target until reached or blocked."""
    state = "advanced"
    while state == "advanced":
        state = extend(tree, target)
    return state


def branch(tree, i):
    out = []
    while i is not None:
        node, i = tree[i]
        out.append(node)
    return out


def plan(seed):
    rng = np.random.default_rng(seed)
    a, b = [(START, None)], [(GOAL, None)]
    for k in range(1, MAX_ITER + 1):
        sample = rng.uniform(0.0, SIZE, 2)
        if extend(a, sample) != "trapped":
            if connect(b, a[-1][0]) == "reached":
                pa = branch(a, len(a) - 1)
                pb = branch(b, len(b) - 1)
                path = pa[::-1] + pb[1:]
                if np.allclose(path[0], GOAL):
                    path = path[::-1]
                if np.allclose(a[0][0], START):
                    return k, (a, b), path
                return k, (b, a), path
        a, b = b, a
    return MAX_ITER, (a, b), None


def edges(tree):
    """Each node with its parent, as [[x, y], [x, y]] pairs."""
    return [[tree[i][0].tolist(), node.tolist()]
            for node, i in tree if i is not None]


def length(path):
    return sum(np.linalg.norm(q - p) for p, q in zip(path, path[1:]))


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "rrt_seed1.json"
    best = length([np.array(c, dtype=float) for c in CORNERS])
    print(f"shortest route around the walls: {best:.2f} m")
    print("seed  samples  start tree  goal tree  path length")
    for seed in range(1, 6):
        k, (ts, tg), path = plan(seed)
        print(f"{seed:4d}  {k:7d}  {len(ts):10d}  {len(tg):9d}  "
              f"{length(path):9.2f} m")
        if seed == 1:
            data = {"walls": WALLS, "start": START.tolist(),
                    "goal": GOAL.tolist(),
                    "edges_start": edges(ts), "edges_goal": edges(tg),
                    "path": [p.tolist() for p in path]}
            with open(out, "w") as fh:
                json.dump(data, fh)


if __name__ == "__main__":
    main()
