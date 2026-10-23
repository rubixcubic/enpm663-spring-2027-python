#!/usr/bin/env bash
# Runs every L6 example and writes its output to ../outputs/.
# env -i drops this shell's ROS and Python paths. The planning demos
# need a venv with the planner (versions in ../outputs/versions.txt):
#   python3 -m venv <venv>
#   <venv>/bin/pip install unified-planning up-fast-downward
# Then run: VENV=<venv> ./run_all.sh
set -euo pipefail
cd "$(dirname "$0")"
: "${VENV:?set VENV to the venv folder with unified-planning}"
ENV=(env -i HOME="$HOME" PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1)
PY=("${ENV[@]}" "$VENV/bin/python")
SYS=("${ENV[@]}" /usr/bin/python3)
OUT=../outputs
FD="$("${PY[@]}" -c 'import os, up_fast_downward as u
print(os.path.join(os.path.dirname(u.__file__), "downward",
                   "fast-downward.py"))')"

{
  "${SYS[@]}" -c "import sys; print('system Python', sys.version[:6])"
  "${PY[@]}" -c "import sys; print('venv Python', sys.version[:6])"
  "${PY[@]}" -c "from importlib.metadata import version as v
for p in ('unified-planning', 'up-fast-downward'): print(p, v(p))"
  "${PY[@]}" "$FD" --version | head -1
} > $OUT/versions.txt

"${PY[@]}" plan_kit.py > $OUT/plan_kit.txt 2>&1
"${PY[@]}" validate_plan.py > $OUT/validate_plan.txt 2>&1
"${PY[@]}" gen_problem.py > $OUT/gen_problem.txt 2>&1
"${PY[@]}" mistakes.py > $OUT/mistakes.txt 2>&1
"${PY[@]}" compare_planners.py > $OUT/compare_planners.txt 2>&1
"${PY[@]}" numeric_try.py > $OUT/numeric_try.txt 2>&1
"${SYS[@]}" select_cells.py > $OUT/select_cells.txt 2>&1
"${SYS[@]}" kit_margin.py > $OUT/kit_margin.txt 2>&1

# Fast Downward from the command line: A* with LM-cut on both
# problems, and the number of ground actions of each kind.
TMP="$(mktemp -d)"
: > $OUT/fd_summary.txt
for run in "problem.pddl small" "$OUT/problem_large.pddl large"
do
  set -- $run
  "${PY[@]}" "$FD" --sas-file "$TMP/$2.sas" --keep-sas-file \
    --plan-file "$OUT/fd_$2.plan" domain.pddl "$1" \
    --search "astar(lmcut())" > "$OUT/fd_$2.log" 2>&1
  echo "$2 problem:" >> $OUT/fd_summary.txt
  grep -e 'Translator operators' -e 'Plan length' \
    -e 'Expanded [0-9]' -e 'Search time' "$OUT/fd_$2.log" \
    | sed 's/^\[t=[^]]*\] //; s/^/  /' >> $OUT/fd_summary.txt
  grep -A1 begin_operator "$TMP/$2.sas" | grep -v -e begin -e '^--' \
    | awk '{print $1}' | sort | uniq -c > "$TMP/$2.count"
done
join -1 2 -2 2 <(sort -k2 "$TMP/small.count") \
  <(sort -k2 "$TMP/large.count") \
  | awk 'BEGIN {printf "%-19s %5s %6s\n", "action", "small", "large"}
         {printf "%-19s %5d %6d\n", $1, $2, $3; s += $2; l += $3}
         END {printf "%-19s %5d %6d\n", "total", s, l}' \
  > $OUT/ground_actions.txt
rm -rf "$TMP"

cat $OUT/versions.txt
