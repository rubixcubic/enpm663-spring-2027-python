#!/usr/bin/env bash
# Runs every L11 example and writes its output to ../outputs/.
# All four are plain Python (py_trees 2.6.0 from ros-jazzy-py-trees,
# jsonschema 4.10.3 from Ubuntu's python3-jsonschema). env -i drops
# this shell's ROS and Python paths. llm_output_checker.py imports
# L8's orchestrator, skill_tools and fake_tools from ../../lecture8/code.
set -euo pipefail
cd "$(dirname "$0")"
run() {
  local out=$1; shift
  env -i HOME="$HOME" PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 \
    bash -c "source /opt/ros/jazzy/setup.bash && $*" > "../outputs/$out" 2>&1
  echo "== $out"; cat "../outputs/$out"
}
run recovery_tree.txt      /usr/bin/python3 recovery_tree.py
run timeout_demo.txt       /usr/bin/python3 timeout_demo.py
run llm_output_checker.txt /usr/bin/python3 llm_output_checker.py
run tester_watcher.txt     /usr/bin/python3 tester_watcher.py
env -i HOME="$HOME" PATH=/usr/bin:/bin bash -c \
  'source /opt/ros/jazzy/setup.bash && /usr/bin/python3 -c "
import sys
from importlib.metadata import version
print(\"Python\", sys.version.split()[0])
print(\"py_trees\", version(\"py_trees\"))
print(\"jsonschema\", version(\"jsonschema\"))
"' > ../outputs/versions.txt
echo "== versions.txt"; cat ../outputs/versions.txt
