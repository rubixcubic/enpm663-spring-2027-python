#!/usr/bin/env bash
# Rerun this lecture's scripts that need no ROS 2, in the uv environment, and rewrite outputs/.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$(dirname "$0")/code"
PY=(uv run --project "$ROOT" --quiet python)
run() { local out=$1; shift; "${PY[@]}" toy_factory.py "$@" > "../outputs/$out" 2>&1; }

"${PY[@]}" -c "import sys; print('Python', sys.version.split()[0])" \
  > ../outputs/versions.txt
run summary.txt
run plan_only.txt      --arch "plan only"
run react_only.txt     --arch "react only"
run three_layers.txt   --arch "three layers"
run no_malfunction.txt --no-malfunction
run sweep.txt          --sweep 1000
run sweep_off.txt      --sweep 1000 --no-malfunction
