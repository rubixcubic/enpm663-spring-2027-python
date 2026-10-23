#!/usr/bin/env bash
# Rerun this lecture's scripts that need no ROS 2, in the uv environment, and rewrite outputs/.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$(dirname "$0")/code"
PY=(uv run --project "$ROOT" --quiet python)
run() { local out=$1; shift; "${PY[@]}" "$@" > "../outputs/$out" 2>&1; }

echo "skipped pc2_roundtrip.py: ROS 2 script, not in this repo (outputs: pc2_roundtrip.txt)"
run point_count.txt      point_count.py
run calibrate.txt        calibrate.py
run detect_one.txt       detect_one.py ../outputs/residuals.csv
run precision_recall.txt precision_recall.py
run voltage_average.txt  voltage_average.py
run timing.txt           timing.py
if [[ -n "${ARIAC_SRC:-}" && -d "$ARIAC_SRC" ]]; then
  run mesh_depths.txt mesh_depths.py "$ARIAC_SRC"
else
  echo "skipped mesh_depths.py: needs ARIAC_SRC (ARIAC 2025 source checkout), not available here (outputs: mesh_depths.txt)"
fi
echo "skipped versions.txt: needs ROS 2 (the ROS 2 distro line) (outputs: versions.txt)"
