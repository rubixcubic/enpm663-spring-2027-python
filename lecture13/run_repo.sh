#!/usr/bin/env bash
# Rerun this lecture's scripts that need no ROS 2, in the uv environment, and rewrite outputs/.
# er_demo.py and score_er.py --scripted are the offline, no-key, no-network parts (as
# run_all.sh runs them). The two recorded runs need outputs/raw/er_rec1 and
# outputs/raw/er_rec2, which this repo does not have (outputs/raw/ is never committed).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$(dirname "$0")/code"
PY=(uv run --project "$ROOT" --quiet python)

"${PY[@]}" -c \
  "import sys; from importlib.metadata import version as v; print('Python', sys.version.split()[0], 'google-genai', v('google-genai'), 'httpx', v('httpx'), 'jsonschema', v('jsonschema'))" \
  > ../outputs/versions.txt
"${PY[@]}" er_demo.py > ../outputs/er_demo.txt 2>&1
"${PY[@]}" score_er.py --scripted > ../outputs/score_er.txt 2>&1
for rec in er_rec1 er_rec2; do
  if [[ -d ../outputs/raw/$rec ]]; then
    "${PY[@]}" score_er.py ../outputs/raw/$rec > ../outputs/score_$rec.txt 2>&1
  else
    echo "skipped score_er.py $rec: needs outputs/raw/$rec, never committed (outputs: score_$rec.txt)"
  fi
done
if [[ -f listings_l13.json ]]; then
  "${PY[@]}" listings_l13.py build listings_l13.json \
    || echo "skipped listings_l13.py build run1_answers/run2_table/run2_rates/run2_cost: need score_er_rec1.txt/score_er_rec2.txt, which need outputs/raw/, never committed (outputs: listings/run1_answers.txt listings/run2_table.txt listings/run2_rates.txt listings/run2_cost.txt)"
fi
echo "skipped pytest tests: run separately in Step 5"
echo "skipped tests/test_run_er_session.sh: not in this repo"
