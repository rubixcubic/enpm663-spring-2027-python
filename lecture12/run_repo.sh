#!/usr/bin/env bash
# Rerun this lecture's scripts that need no ROS 2, in the uv environment, and rewrite outputs/.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$(dirname "$0")/code"
PY=(uv run --project "$ROOT" --quiet python)
run() { local out=$1; shift; "${PY[@]}" "$@" > "../outputs/$out" 2>&1; }

run score_runs.txt     score_calculator.py
run success_spread.txt success_spread.py
run perception.txt     perception_metrics.py
run batch_bar.txt      batch_bar.py
"${PY[@]}" -c \
  'import sys, numpy, yaml; v = sys.version.split()[0]
print("Python", v);
print("numpy", numpy.__version__)
print("PyYAML", yaml.__version__)' \
  > ../outputs/versions.txt
