"""ARIAC 2025 run score, computed the way ariac_db/scoring.py does.

The weights come from scoring_weights.yaml, copied from the ARIAC
source (branch ariac2025, commit 0c3e722). The sensor prices come from
the ARIAC sensors page. Every run measurement (times, counts) is
chosen for this example.

Writes a text report to stdout and the score terms to
../outputs/score_runs.json (read by the bar chart figure).
"""
import json
import pathlib

import yaml

HERE = pathlib.Path(__file__).parent
CFG = yaml.safe_load((HERE / "scoring_weights.yaml").read_text())
W = CFG["WEIGHTS"]
PEN = CFG["PENALTIES"]
BUDGET = CFG["SENSOR_BUDGET"]                          # dollars
GAMMA_D = CFG["NOMINAL_INSPECTION_TIME"]               # seconds
TAU_D = CFG["NOMINAL_HIGH_PRIORITY_EXECUTION_DURATION"]  # seconds

# Sensor prices from the ARIAC sensors page; the choice is ours.
SENSORS = [
    ("lidar, grade B", 1250),
    ("lidar, grade B", 1250),
    ("break beam, grade A", 400),
    ("camera, 1080p", 800),
]


def base(run):
    kits = mods = 0.0  # a trial with no kits or no modules adds 0 for them
    if run["kits_wanted"] > 0:
        kits = W["W1"] * run["kits_done"] / run["kits_wanted"]
    if run["modules_wanted"] > 0:
        mods = W["W2"] * run["modules_done"] / run["modules_wanted"]
    return kits + mods


def bonuses(run):
    done = (run["kits_done"] == run["kits_wanted"]
            and run["modules_done"] == run["modules_wanted"])
    if not done:  # ARIAC marks the run aborted: every bonus is 0
        return dict.fromkeys(
            ["trial time", "inspection speed", "high-priority speed",
             "sensor cost", "classification"], 0.0)
    b = {}
    # Not clamped in scoring.py: below 0 only if te > tm.
    b["trial time"] = W["W3"] * (1 - run["te"] / run["tm"])
    b["inspection speed"] = max(
        0, W["W4"] * (1 - run["report_s"] / GAMMA_D))
    hp = run["hp_s"]
    b["high-priority speed"] = 0.0 if not hp else max(
        0, W["W5"] * (1 - sum(hp) / len(hp) / TAU_D))
    b["sensor cost"] = max(0, W["W6"] * (1 - run["cost"] / BUDGET))
    b["classification"] = 0.0 if run["defective"] == 0 else (
        W["W7"] * run["correct"] / run["defective"])
    return b


def penalties(run):
    p = {key: PEN[key] * n for key, n in run["events"].items()}
    p["SENSOR_OVER_BUDGET"] = max(
        0, W["W6"] * (run["cost"] / BUDGET - 1))
    return p


def score(run):
    b, p = bonuses(run), penalties(run)
    total = base(run) + sum(b.values()) - sum(p.values())
    return b, p, total


def terms(run):
    b, p, total = score(run)
    return {"base": base(run), "bonuses": b,
            "penalties": sum(p.values()), "score": total}


def rows(t):
    yield "base", t["base"]
    for name, value in t["bonuses"].items():
        yield "bonus " + name, value
    yield "penalties", t["penalties"]
    yield "run score", t["score"]


cost = sum(price for _, price in SENSORS)
run_1 = {
    "kits_wanted": 3, "kits_done": 3,      # 2 kits + 1 high priority
    "modules_wanted": 0, "modules_done": 0,
    "tm": 900, "te": 630,                  # seconds
    "report_s": 3.0, "hp_s": [120.0],      # seconds
    "cost": cost, "defective": 4, "correct": 3,
    "events": {"GOOD_CELL_IN_INSPECTION_BIN": 1,
               "ROBOT_COLLISION": 1},
}
run_2 = dict(run_1, kits_done=2, hp_s=[])  # high priority missed

print(f"Sensor cost: ${cost} (budget ${BUDGET})")
r1, r2 = terms(run_1), terms(run_2)
print(f"{'term':<27}{'Run 1':>8}{'Run 2':>8}")
for (name, a), (_, b) in zip(rows(r1), rows(r2)):
    print(f"{name:<27}{a:>8.1f}{b:>8.1f}")
lost_base = r1["base"] - r2["base"]
lost_bonus = sum(r1["bonuses"].values())
print(f"Run 1 minus Run 2: {r1['score'] - r2['score']:.2f}"
      f" = base {lost_base:.2f} + bonuses {lost_bonus:.2f}")
over = dict(run_1, cost=10400)
print(f"Over-budget penalty at $10400: "
      f"{penalties(over)['SENSOR_OVER_BUDGET']:.1f}")

out = HERE.parent / "outputs" / "score_runs.json"
out.write_text(json.dumps({"run_1": r1, "run_2": r2}, indent=2)
               + "\n")
