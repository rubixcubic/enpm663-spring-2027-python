#!/usr/bin/env bash
# Rerun this lecture's scripts that need no ROS 2, in the uv environment, and rewrite outputs/.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$(dirname "$0")/code"
PY=(uv run --project "$ROOT" --quiet python)
run() { local out=$1; shift; "${PY[@]}" "$@" > "../outputs/$out" 2>&1; }

echo "skipped tf_agv_moves.py: ROS 2 script, not in this repo (outputs: tf_agv_moves.txt)"
echo "skipped tf_failures.py: ROS 2 script, not in this repo (outputs: tf_failures.txt)"
echo "skipped pixel_to_table.py: ROS 2 script, not in this repo (outputs: pixel_to_table.txt)"
run conveyor_intercept.txt conveyor_intercept.py
run rrt_connect.txt        rrt_connect_toy.py ../outputs/rrt_seed1.json
echo "skipped versions.txt: needs ROS 2 (the ROS 2 distro line) (outputs: versions.txt)"
