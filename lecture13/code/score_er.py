"""L13: score the embodied-reasoning answers.

Two modes.

Recorded run (python3 score_er.py [RAW_DIR]; default ../outputs/raw/er_rec1):
the real answers of gemini-robotics-er-2-preview on 12 real ARIAC camera
images, recorded once by er_session.py, scored against ARIAC's own cell
log (log_cell_info:=true). No key and no network: it reads the recording.
  TRUTH  the defect types ARIAC logged for each cell (cell_info.txt).
  ER     the defect types in the model's schema-valid answer.
A cell can have two defects (defects.yaml sets 4, 7, 8, 9, 10), so each
label is a set of types. No lidar detector ran in this session.
It also prints, for each logged defect, how far it points away from the
camera and where it lands in the image (pinhole model, as in L10), and the
tokens, latency and cost of every call.

Scripted example (python3 score_er.py --scripted): three labels per cell,
all chosen for this example:
  TRUTH  what the cell really has. In a practice run, ARIAC prints it
         to the Gazebo log when launched with log_cell_info:=true.
  LIDAR  the defect type in the team's GP2 inspection report.
  ER     the defect type from er_demo.py (a scripted stand-in).
Each defective cell in this example has one defect.

Only cells where both detectors gave a valid answer are scored, so
both are scored on the same cells.

Run: python3 score_er.py   (needs google-genai and jsonschema)
"""

import json
import math
import re
import sys
from pathlib import Path

TRUTH = {"c01": None, "c02": "DENT", "c03": None, "c04": "SCRATCH",
         "c05": None, "c06": "BULGE", "c07": "DENT", "c08": None,
         "c09": "SCRATCH", "c10": None, "c11": "BULGE", "c12": None}
LIDAR = {"c01": None, "c02": "DENT", "c03": None, "c04": "SCRATCH",
         "c05": None, "c06": "BULGE", "c07": "DENT", "c08": None,
         "c09": None, "c10": None, "c11": "BULGE", "c12": None}
TYPES = ["DENT", "SCRATCH", "BULGE"]


def er_labels(results):
    """One label per cell with a valid answer; None if no defect."""
    labels, rejected = {}, []
    for cell, (_, answer, errors) in results.items():
        if errors:
            rejected.append(cell)
            continue
        kinds = [d["type"] for d in answer["defects"]]
        labels[cell] = kinds[0] if kinds else None
    return labels, rejected


def counts(pred, cells, kind):
    """True positives, false positives, false negatives for a kind."""
    tp = sum(pred[c] == kind and TRUTH[c] == kind for c in cells)
    fp = sum(pred[c] == kind and TRUTH[c] != kind for c in cells)
    fn = sum(pred[c] != kind and TRUTH[c] == kind for c in cells)
    return tp, fp, fn


def ratio(num, den):
    return f"{num}/{den} = {num / den:.2f}" if den else "no calls"


def row(name, pred, cells, kind):
    tp, fp, fn = counts(pred, cells, kind)
    print(f"  {name:6} TP {tp}  FP {fp}  FN {fn}   "
          f"precision {ratio(tp, tp + fp):12}  "
          f"recall {ratio(tp, tp + fn)}")


def scripted_main():
    from er_demo import ask_all
    _, results = ask_all()
    er, rejected = er_labels(results)
    cells = [c for c in TRUTH if c in er]
    print(f"Cells used: {len(cells)} of {len(TRUTH)}")
    print(f"  rejected by the schema: {', '.join(rejected)}")
    for kind in TYPES:
        print(f"{kind}")
        row("lidar", LIDAR, cells, kind)
        row("ER", er, cells, kind)
    same = sum(er[c] == LIDAR[c] for c in cells)
    print(f"ER and lidar give the same label: {same} of {len(cells)}")
    print("Latency and cost per call: not measured (stand-in)")


# ---------------------------------------------------------------- the recorded run

LOG_TYPES = {"Dent": "DENT", "Bulge": "BULGE", "Scratch": "SCRATCH"}   # cheat_tools_plugin.cpp:143-151
# Prices: https://ai.google.dev/gemini-api/docs/pricing, read 2026-10-18 (Last updated
# 2026-10-16 UTC), gemini-robotics-er-2-preview, paid tier, per 1M tokens: input "$1.00
# (text / image / video / audio) through December 31, 2026", output "$5.00 through
# December 31, 2026" under "Output price (including thinking tokens)". Free tier: "Free of charge".
PRICE_IN, PRICE_OUT = 1.00, 5.00
# The same rows continue (same page, same date): input "$2.00 (text / image / video / audio)
# starting January 1, 2027", output "$10.00 starting January 1, 2027". The Spring 2027
# semester runs under these.
PRICE_IN_2027, PRICE_OUT_2027 = 2.00, 10.00
Z95 = 1.96   # the normal quantile for a 95% interval

# Camera, from config/l13_user_config.yaml and ARIAC's camera model (structures.py Camera,
# sensors/camera/model.sdf): the view axis is the camera's +x, the image's left its +y and
# the image's top its +z.
CAM_XYZ = (0.8, 1.188, 0.525)
CAM_PITCH, CAM_YAW = 0.349, -math.pi / 2
WIDTH, HEIGHT, HFOV = 1920, 1080, 0.873
CELL_Y, BELT_Z, CELL_RADIUS = 1.0, 0.422, 0.0105   # m: belt center line, belt top, cell radius
TOWARD_CAMERA = math.pi / 2   # rad: the camera is on the +y side of the cell


def parse_cell_info(text):
    """{ariac name: {"defective": bool, "set": int or None, "defects": [...]}} from cell_info.txt.

    Each defect: {"type", "relative", "absolute", "z"} as logged (radians, meters)."""
    cells, cur, defect = {}, None, None
    for line in text.splitlines():
        m = re.fullmatch(r"Cell (\S+):", line.strip())
        if m:
            cur = cells[m.group(1)] = {"defective": None, "set": None, "defects": []}
            continue
        body = line.strip()
        if cur is None or not body:
            continue
        if body.startswith("- Type:"):
            defect = {"type": LOG_TYPES.get(body.split(":", 1)[1].strip())}
            cur["defects"].append(defect)
        elif body.startswith("Defective:"):
            cur["defective"] = body.endswith("True")
        elif body.startswith("Defect type:"):
            cur["set"] = int(body.split(":", 1)[1])
        elif defect is not None and body.startswith("Relative theta:"):
            defect["relative"] = float(body.split(":", 1)[1])
        elif defect is not None and body.startswith("Absolute theta:"):
            defect["absolute"] = float(body.split(":", 1)[1])
        elif defect is not None and body.startswith("Z:"):
            defect["z"] = float(body.split(":", 1)[1])
    return cells


def mesh_depths(path):
    """{(set, type, yaml theta rounded to 3 places): depth in mm} from L5's mesh_depths.txt."""
    out = {}
    if not Path(path).exists():
        return out
    for line in Path(path).read_text().splitlines():
        p = line.split()
        if len(p) == 5 and p[0].isdigit():
            out[(int(p[0]), p[1].upper(), round(float(p[2]), 3))] = float(p[4])
    return out


def wilson(k, n, z=Z95):
    """The Wilson score interval for k of n (no interval for n = 0)."""
    if n == 0:
        return None
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z / (1 + z * z / n) * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return max(0.0, centre - half), min(1.0, centre + half)


def rate(k, n):
    """'k/n = r (95% interval a to b)', or '0/0, not defined' for n = 0."""
    if n == 0:
        return "0/0, not defined"
    lo, hi = wilson(k, n)
    return f"{k}/{n} = {k / n:.2f} (95% interval {lo:.2f} to {hi:.2f})"


def set_counts(pred, truth, cells, kind):
    """TP, FP, FN for one type when each label is a set of types."""
    tp = sum(kind in pred[c] and kind in truth[c] for c in cells)
    fp = sum(kind in pred[c] and kind not in truth[c] for c in cells)
    fn = sum(kind not in pred[c] and kind in truth[c] for c in cells)
    return tp, fp, fn


def one_cell(tp, n):
    """What one cell changes in a rate of tp out of n."""
    if n == 0:
        return "no cell to move"
    lo, hi = max(tp - 1, 0), min(tp + 1, n)
    return f"one cell more or less moves it from {tp}/{n} to {lo}/{n} or {hi}/{n} ({1 / n:.2f} a cell)"


def angle_from_camera(absolute):
    """Degrees between the defect's outward direction and the direction to the camera."""
    d = absolute - TOWARD_CAMERA
    return abs(math.degrees(math.atan2(math.sin(d), math.cos(d))))


def project(x, y, z):
    """World point to (row, column) in pixels, pinhole model; None if behind the camera."""
    cx, cy, cz = CAM_XYZ
    dx, dy, dz = x - cx, y - cy, z - cz
    # world to camera: R = Rz(yaw) Ry(pitch), so p_cam = Ry(pitch)^T Rz(yaw)^T d
    cyaw, syaw = math.cos(CAM_YAW), math.sin(CAM_YAW)
    ux, uy = cyaw * dx + syaw * dy, -syaw * dx + cyaw * dy
    cp, sp = math.cos(CAM_PITCH), math.sin(CAM_PITCH)
    fwd, left, up = cp * ux - sp * dz, uy, sp * ux + cp * dz
    if fwd <= 0:
        return None
    f = (WIDTH / 2) / math.tan(HFOV / 2)
    return (HEIGHT / 2 - f * up / fwd, WIDTH / 2 - f * left / fwd)


def defect_pixel(cell_x, defect):
    a = defect["absolute"]
    return project(cell_x + CELL_RADIUS * math.cos(a), CELL_Y + CELL_RADIUS * math.sin(a),
                   BELT_Z + defect["z"])


def billed_output(i, o, t, tot):
    """Output tokens billed at the output price, thinking included.

    The API reference (https://ai.google.dev/api/interactions-api, read 2026-10-18)
    defines total_output_tokens as "Total number of tokens across all the generated
    responses" and total_thought_tokens as "Number of tokens of thoughts", but does not
    say whether the first holds the second. The totals decide: when total_tokens is
    input + output + thought, the thoughts are separate and are added."""
    if tot == i + o + t:
        return o + t
    if tot == i + o:
        return o
    raise ValueError(f"total_tokens {tot} is neither {i} + {o} + {t} nor {i} + {o}")


FENCE = re.compile(r"\A```json\n(.*)\n```\Z", re.S)


def strip_fence(text):
    """The text inside one Markdown code fence (```json ... ```), else the text unchanged.
    This is NOT the deck's check: check() reads the answer exactly as the model sent it."""
    m = FENCE.match(text.strip())
    return m.group(1) if m else text


def labels(cells, answers, check, read=lambda t: t):
    """{cell: set of types} for the schema-valid answers, the rejected cells with their
    errors, and the cells with no answer."""
    pred, rejected, failed = {}, [], []
    for c in cells:
        rec = answers.get(c)
        if rec is None or rec.get("text") is None:
            failed.append(c)
            continue
        answer, errors = check(read(rec["text"]))
        if errors:
            rejected.append((c, errors))
            continue
        pred[c] = ({d["type"] for d in answer["defects"]}, answer)
    return pred, rejected, failed


def score(title, cells, truth, pred, rejected, failed, answers):
    used = [c for c in cells if c in pred]
    kinds = {c: pred[c][0] for c in used}
    print()
    print(title)
    print("cell  ARIAC (log)    model answer")
    for c in cells:
        t = ", ".join(sorted(truth[c])) or "none"
        if c in pred:
            shown = ", ".join(sorted(kinds[c])) or "none"
        elif c in failed:
            shown = "no answer: " + ((answers.get(c) or {}).get("error") or "not sent")[:48]
        else:
            shown = "rejected by the schema"
        print(f"{c}   {t:14} {shown}")
    print(f"Cells used: {len(used)} of {len(cells)}")
    for c, errors in rejected:
        print(f"  {c} rejected by the schema: {errors[0][:60]}")
    for c in failed:
        print(f"  {c} has no answer")
    print("Per defect type, over the cells used (95% intervals: Wilson score)")
    for kind in TYPES:
        tp, fp, fn = set_counts(kinds, truth, used, kind)
        print(f"{kind}: TP {tp}  FP {fp}  FN {fn}")
        print(f"  precision {rate(tp, tp + fp)}")
        print(f"  recall    {rate(tp, tp + fn)}")
        print(f"  recall: {one_cell(tp, tp + fn)}")
    any_pred = {c: {"ANY"} if kinds[c] else set() for c in used}
    any_truth = {c: {"ANY"} if truth[c] else set() for c in used}
    tp, fp, fn = set_counts(any_pred, any_truth, used, "ANY")
    print(f"Any defect (the cell is defective): TP {tp}  FP {fp}  FN {fn}")
    print(f"  precision {rate(tp, tp + fp)}")
    print(f"  recall    {rate(tp, tp + fn)}")
    return kinds


def recorded_main(raw_dir):
    from er_demo import check
    raw = Path(raw_dir)
    name = raw.name
    head = (raw.parent.parent / f"{name}.txt").read_text().splitlines()
    date = next((h.split(": ", 1)[1].split()[0] for h in head if h.startswith("date: ")), "?")
    captures = json.loads((raw / "captures.json").read_text())
    info = parse_cell_info((raw / "cell_info.txt").read_text())
    answers = json.loads((raw / "answers.json").read_text())
    depths = mesh_depths(Path(__file__).resolve().parents[2] / "lecture5" / "outputs" / "mesh_depths.txt")
    models = sorted({m for f in raw.glob("c*.response.json")
                     if (m := json.loads(f.read_text()).get("model"))})
    print(f"Recorded once, on {date}, with {', '.join(models) or 'no model response'}. "
          "A rerun gives different answers.")
    print(f"Recording: outputs/raw/{name}; ground truth: ARIAC's cell log (log_cell_info:=true)")

    cells = [c["cell"] for c in captures]
    truth = {c["cell"]: {d["type"] for d in info[c["ariac_name"]]["defects"]} for c in captures}
    score("1. The deck's schema check, on the answers as sent", cells, truth,
          *labels(cells, answers, check), answers)
    texts = [r["text"] for r in answers.values() if r.get("text") is not None]
    if any(strip_fence(t) != t for t in texts):
        fenced = labels(cells, answers, check, strip_fence)
        kinds = score("2. Not the deck's check: the same answers with the ```json fence removed",
                      cells, truth, *fenced, answers)
        pred, table = fenced[0], 2
    else:
        print()
        print("2. No answer had a ```json fence: the tables below use table 1")
        pred, _, _ = labels(cells, answers, check)
        kinds, table = {c: pred[c][0] for c in pred}, 1

    print()
    print("Each logged defect: depth (L5 mesh), angle from the camera, image position")
    print(f"(model named the type: from table {table}). The pinhole position is approximate:")
    print("it puts c01's cell center about 80 px (about 8 mm) right of where the image shows it.")
    print("cell  type     set  Z mm  depth mm  deg from camera  ~row, col px  model named the type")
    for cap in captures:
        c, entry = cap["cell"], info[cap["ariac_name"]]
        for d in entry["defects"]:
            depth = depths.get((entry["set"], d["type"], round(d["relative"], 3)))
            px = defect_pixel(cap["cell_x_m"], d)
            named = "yes" if c in kinds and d["type"] in kinds[c] else ("no" if c in kinds else "no answer")
            where = f"{px[0]:4.0f}, {px[1]:4.0f}" if px else "behind"
            dep = f"{depth:+.2f}" if depth is not None else "?"
            print(f"{c}   {d['type']:8} {entry['set']:3}  {d['z'] * 1000:4.1f}  {dep:>8}  "
                  f"{angle_from_camera(d['absolute']):15.0f}  {where:11}  {named}")

    print()
    print(f"Points the model gave (table {table}), [y, x] in 0 to 1000, and as row, col px")
    for c in cells:
        if c not in pred:
            continue
        for d in pred[c][1]["defects"]:
            y, x = d["point"]
            print(f"{c}   {d['type']:8} [{y}, {x}]  {y * HEIGHT / 1000:4.0f}, {x * WIDTH / 1000:4.0f}")

    print()
    print(f"Tokens, latency and cost per call (${PRICE_IN:.2f} and ${PRICE_OUT:.2f} per 1M input and output")
    print("tokens, paid tier through 2026-12-31; output billed with thinking tokens)")
    print("cell  input  output  thought  total  wall s   cost $")
    total = [0, 0, 0, 0, 0.0, 0.0]
    cost_2027 = 0.0
    n = 0
    for c in cells:
        f = raw / f"{c}.response.json"
        rec = answers.get(c)
        if not f.exists():
            print(f"{c}   not sent")
            continue
        u = json.loads(f.read_text()).get("usage")
        if not u:
            print(f"{c}   no usage: HTTP {rec['http_status']} after {rec['latency_s']:.2f} wall s")
            continue
        i, o, t = (u.get("total_input_tokens") or 0, u.get("total_output_tokens") or 0,
                   u.get("total_thought_tokens") or 0)
        tot = u.get("total_tokens") or 0
        cost = (i * PRICE_IN + billed_output(i, o, t, tot) * PRICE_OUT) / 1e6
        cost_2027 += (i * PRICE_IN_2027 + billed_output(i, o, t, tot) * PRICE_OUT_2027) / 1e6
        lat = rec["latency_s"]
        n += 1
        for k, v in enumerate((i, o, t, tot, lat, cost)):
            total[k] += v
        print(f"{c}   {i:5}  {o:6}  {t:7}  {tot:5}  {lat:6.2f}  {cost:.6f}")
    print(f"all   {total[0]:5}  {total[1]:6}  {total[2]:7}  {total[3]:5}  {total[4]:6.2f}  {total[5]:.6f}")
    if n:
        print(f"mean per answered call: {total[4] / n:.2f} wall s, ${total[5] / n:.6f}")
        print(f"at the prices from 2027-01-01 (${PRICE_IN_2027:.2f} and ${PRICE_OUT_2027:.2f} per 1M, "
              f"same page): all ${cost_2027:.6f}, mean ${cost_2027 / n:.6f}")
    print("Free tier: free of charge (same pricing page).")


if __name__ == "__main__":
    if sys.argv[1:] == ["--scripted"]:
        scripted_main()
    elif len(sys.argv) <= 2:
        here = Path(__file__).resolve().parent
        recorded_main(sys.argv[1] if len(sys.argv) == 2 else here.parent / "outputs" / "raw" / "er_rec1")
    else:
        sys.exit("usage: score_er.py [RAW_DIR] | score_er.py --scripted")
