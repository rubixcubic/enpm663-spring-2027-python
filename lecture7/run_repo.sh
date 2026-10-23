#!/usr/bin/env bash
# Rerun this lecture's scripts that need no ROS 2, in the uv environment, and rewrite outputs/.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$(dirname "$0")/code"
PY=(uv run --project "$ROOT" --quiet python)
run() { local out=$1; shift; "${PY[@]}" "$@" > "../outputs/$out" 2>&1; }

for mode in build tick trace unknown nomemory noguard; do
  run "factory_$mode.txt" demo_factory.py "$mode"
done
run retry_2.txt demo_retry.py 2
run retry_3.txt demo_retry.py 3
for mode in normal silent malfunction; do
  run "timeout_$mode.txt" demo_timeout.py "$mode"
done
run nesting_hang.txt demo_nesting.py hang --starts
run nesting_fail.txt demo_nesting.py fail
run replan.txt demo_replan.py
for n in 1 3; do
  run "pytrees_$n.txt" demo_place_cell.py "$n"
done
echo "skipped btcpp_1.txt: needs g++ and ROS 2's BehaviorTree.CPP headers/libs, not in the manifest (outputs: btcpp_1.txt)"
echo "skipped btcpp_3.txt: needs g++ and ROS 2's BehaviorTree.CPP headers/libs, not in the manifest (outputs: btcpp_3.txt)"
echo "skipped versions.txt: needs ROS 2 (py_trees via ROS source), g++ and BehaviorTree.CPP (outputs: versions.txt)"
