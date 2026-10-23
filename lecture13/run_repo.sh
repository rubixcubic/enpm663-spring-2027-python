#!/usr/bin/env bash
# Rerun this lecture's scripts that need no ROS 2, in the uv environment, and rewrite outputs/.
# er_demo.py and score_er.py --scripted are the offline, no-key, no-network parts (as
# the slides repo's code/run_all.sh runs them). The two recorded runs need
# outputs/raw/er_rec1 and outputs/raw/er_rec2, which this repo does not have
# (outputs/raw/ is never committed).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$(dirname "$0")/code"
PY=(uv run --project "$ROOT" --quiet python)

echo "skipped versions.txt: measured in the L13 venv with jsonschema 4.26.0; this environment pins 4.10.3 (outputs: versions.txt)"
"${PY[@]}" er_demo.py > ../outputs/er_demo.txt 2>&1
"${PY[@]}" score_er.py --scripted > ../outputs/score_er.txt 2>&1
for rec in er_rec1 er_rec2; do
  if [[ -d ../outputs/raw/$rec ]]; then
    "${PY[@]}" score_er.py ../outputs/raw/$rec > ../outputs/score_$rec.txt 2>&1
  else
    echo "skipped score_er.py $rec: needs outputs/raw/$rec, never committed (outputs: score_$rec.txt)"
  fi
done
# Four listings are cut from score_er_rec1.txt and score_er_rec2.txt. Without both
# files, build only the listings that do not read them, from a copy of the spec
# kept next to listings_l13.json (the build finds outputs/ from the spec's folder).
if [[ -f ../outputs/score_er_rec1.txt && -f ../outputs/score_er_rec2.txt ]]; then
  "${PY[@]}" listings_l13.py build listings_l13.json
else
  OFFLINE="$(mktemp -p . listings_offline.XXXXXX)"
  trap 'rm -f "$OFFLINE"' EXIT
  "${PY[@]}" -c 'import json, sys
spec = json.load(open(sys.argv[1]))
needs = {"score_er_rec1.txt", "score_er_rec2.txt"}
spec["listings"] = [e for e in spec["listings"] if not needs & {p.get("source") for p in e["parts"]}]
json.dump(spec, open(sys.argv[2], "w"))' listings_l13.json "$OFFLINE"
  "${PY[@]}" listings_l13.py build "$OFFLINE"
  rm -f "$OFFLINE"
  echo "skipped listings_l13.py build run1_answers/run2_table/run2_rates/run2_cost: need score_er_rec1.txt and score_er_rec2.txt, which need outputs/raw/, never committed (outputs: listings/run1_answers.txt listings/run2_table.txt listings/run2_rates.txt listings/run2_cost.txt)"
fi
echo "skipped pytest tests: run them by hand with: cd lecture13/code && env -u PYTHONPATH uv run python -m pytest tests"
echo "skipped tests/test_run_er_session.sh: not in this repo"
