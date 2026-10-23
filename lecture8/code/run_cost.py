"""L8: tokens, latency and cost of one recorded run, from its raw API responses.

Prices from gemini_prices.py (quoted from the Gemini pricing page, with the date read).
Run: python3 run_cost.py ../outputs/raw/<name>/raw ../outputs/agent_run1_usage.json
"""
import json
import sys
from pathlib import Path

from gemini_model import billed_output, usage_from_raw
from gemini_prices import MODEL, PRICE_IN, PRICE_OUT, SOURCE


def main(raw_dir, summary_path):
    rows = []
    for f in sorted(Path(raw_dir).glob("call_*[0-9].json")):
        u = usage_from_raw(json.loads(f.read_text()))
        latency = json.loads(f.with_name(f.stem + ".meta.json").read_text())["latency_s"]
        rows.append((int(f.stem.split("_")[1]), u["input"], u["output"], billed_output(u), latency))
    print(f"model {MODEL}; prices {PRICE_IN} and {PRICE_OUT} dollars per million tokens ({SOURCE})")
    print(f"{'call':>4} {'input':>7} {'output':>6} {'billed':>6} {'wall s':>6} {'cost $':>9}")
    total = 0.0
    for n, inp, out, billed, lat in rows:
        cost = (inp * PRICE_IN + billed * PRICE_OUT) / 1e6
        total += cost
        print(f"{n:>4} {inp:>7} {out:>6} {billed:>6} {lat:>6.2f} {cost:>9.6f}")
    tin, tbill = sum(r[1] for r in rows), sum(r[3] for r in rows)
    print(f"total {tin:>7} {sum(r[2] for r in rows):>6} {tbill:>6} {sum(r[4] for r in rows):>6.2f} {total:>9.6f}")
    summary = {"recording": str(raw_dir), "calls": len(rows), "first_input": rows[0][1],
               "last_input": rows[-1][1], "mean_output": round(sum(r[2] for r in rows) / len(rows), 1),
               "input_total": tin, "output_total": sum(r[2] for r in rows),
               "billed_output_total": tbill, "cost": round(total, 6)}
    Path(summary_path).write_text(json.dumps(summary, indent=1) + "\n")


if __name__ == "__main__":
    main(*sys.argv[1:3])
