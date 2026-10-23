#!/usr/bin/env bash
# Runs the L2 toy factory and writes every output to ../outputs/.
# Plain Python, no ROS. env -i drops this shell's Python paths, so
# the system Python is the one used. Fixed seeds: every run repeats.
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p ../outputs
py() { env -i HOME="$HOME" PATH=/usr/bin:/bin /usr/bin/python3 "$@"; }
run() {
  local out=$1; shift
  py toy_factory.py "$@" > "../outputs/$out" 2>&1
  echo "== $out"; cat "../outputs/$out"
}
py -c "import sys; print('Python', sys.version.split()[0])" \
  > ../outputs/versions.txt
run summary.txt
run plan_only.txt      --arch "plan only"
run react_only.txt     --arch "react only"
run three_layers.txt   --arch "three layers"
run no_malfunction.txt --no-malfunction
run sweep.txt          --sweep 1000
run sweep_off.txt      --sweep 1000 --no-malfunction
