#!/usr/bin/env bash
# Rerun this lecture's scripts that need no ROS 2, in the uv environment, and rewrite outputs/.
# run_all.sh sources ROS 2 Jazzy only to get py_trees 2.6.0; the uv environment pins the
# same version, so these five scripts are managed. ros_tree_demo.py talks ROS and is not
# in this repo.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$(dirname "$0")/code"
PY=(uv run --project "$ROOT" --quiet python)
run() { local out=$1; shift; "${PY[@]}" "$@" > "../outputs/$out" 2>&1; }

run retry_demo.txt       retry_demo.py
run composite_status.txt composite_status.py
run parallel_watch.txt   parallel_watch.py
run blackboard_demo.txt  blackboard_demo.py
run kit_spread.txt       kit_spread.py
echo "skipped ros_tree_demo.py ok: ROS 2 script, not in this repo (outputs: ros_tree_ok.txt)"
echo "skipped ros_tree_demo.py timeout: ROS 2 script, not in this repo (outputs: ros_tree_timeout.txt)"
echo "skipped ros_tree_demo.py bad_kit: ROS 2 script, not in this repo (outputs: ros_tree_bad_kit.txt)"
echo "skipped ros_tree_demo.py repeats: ROS 2 script, not in this repo (outputs: ros_tree_repeats.txt)"
echo "skipped ros_tree_demo.py repeat_sets: ROS 2 script, not in this repo (outputs: ros_tree_repeat_sets.txt)"
echo "skipped versions.txt: needs py_trees_ros (ROS), not in the uv environment (outputs: versions.txt)"
