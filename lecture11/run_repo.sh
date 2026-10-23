#!/usr/bin/env bash
# Rerun this lecture's scripts that need no ROS 2, in the uv environment, and rewrite outputs/.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$(dirname "$0")/code"
PY=(uv run --project "$ROOT" --quiet python)
run() { local out=$1; shift; "${PY[@]}" "$@" > "../outputs/$out" 2>&1; }

run recovery_tree.txt      recovery_tree.py
run timeout_demo.txt       timeout_demo.py
run llm_output_checker.txt llm_output_checker.py
run tester_watcher.txt     tester_watcher.py
echo "skipped versions.txt: sources ROS 2 to report the ROS-packaged py_trees and jsonschema versions (outputs: versions.txt)"
