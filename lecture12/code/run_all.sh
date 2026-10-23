#!/usr/bin/env bash
# Runs every L12 example and writes its output to ../outputs/.
# Plain Python, no ROS 2: env -i drops this shell's ROS and Python
# paths so the system Python (/usr/bin/python3) runs each script.
set -euo pipefail
cd "$(dirname "$0")"
run() {
  local out=$1; shift
  env -i HOME="$HOME" PATH=/usr/bin:/bin /usr/bin/python3 "$@" \
    > "../outputs/$out" 2>&1
  echo "== $out"; cat "../outputs/$out"
}
run score_runs.txt     score_calculator.py
run success_spread.txt success_spread.py
run perception.txt     perception_metrics.py
run batch_bar.txt      batch_bar.py
env -i HOME="$HOME" PATH=/usr/bin:/bin /usr/bin/python3 -c \
  'import sys, numpy, yaml; v = sys.version.split()[0]
print("Python", v);
print("numpy", numpy.__version__)
print("PyYAML", yaml.__version__)' \
  > ../outputs/versions.txt
echo "== versions.txt"; cat ../outputs/versions.txt
