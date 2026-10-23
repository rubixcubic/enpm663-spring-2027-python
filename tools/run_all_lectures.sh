#!/usr/bin/env bash
# Rerun every lecture in a scratch copy with its outputs cleared, and compare with the
# committed outputs. Writes tools/run_report.txt. No ROS 2 setup is sourced.
#
# A step the repo cannot run (needs outputs/raw/, an ARIAC source checkout, the Docker
# container or ROS) prints a line of the exact form
#   skipped <script>: <reason> (outputs: <file> [<file> ...])
# tools/_diff_report.py reads that line from the run's log, drops the matching
# "Only in ...: <file>" line from the diff, and reports "<lecture>: not rerun: <file>:
# <reason>" instead. A file whose content varies run to run (not because a step was
# skipped) is listed once in tools/noise.txt; if every file still differing after that
# is in tools/noise.txt, the lecture is reported "identical except noise", with the
# noise diff lines kept below that line. Anything else left differing keeps the lecture
# at DIFFER.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
REPORT=tools/run_report.txt
: > "$REPORT"
SCRATCH=$(mktemp -d)
trap 'rm -rf "$SCRATCH"' EXIT
# R9 recorded inputs: measured runs a managed step reads from outputs/, never written
# by any run_repo.sh step. Kept in one place, as the full path relative to this
# repository, so the pre-run clearing step below excludes each one by its full path,
# not by basename (two lectures' outputs/ trees can otherwise share a basename, for
# example lecture8/outputs/structured_live.txt, the recorded input, and
# lecture8/outputs/listings/structured_live.txt, a real listings.py build output).
RECORDED_INPUTS=(
  lecture8/outputs/agent_rec1.txt
  lecture8/outputs/agent_run1_cost.txt
  lecture8/outputs/agent_run1_usage.json
  lecture8/outputs/mcp_demo.txt
  lecture8/outputs/structured_live.txt
  lecture9/outputs/closed_loop_replan_rec1.txt
  lecture9/outputs/closed_loop_wait_rec1.txt
  lecture13/outputs/er_rec1.txt
  lecture13/outputs/er_rec2.txt
)
# Every lecture folder goes into the scratch copy, so parents[2] / "lecture8" / "code" resolves.
for lec in lecture*/; do /bin/cp -r "${lec%/}" "$SCRATCH/"; done
/bin/cp pyproject.toml uv.lock .python-version "$SCRATCH/"
for lec in lecture*/; do
  lec=${lec%/}
  if [[ ! -f "$lec/run_repo.sh" ]]; then echo "$lec: no run_repo.sh" >> "$REPORT"; continue; fi
  find_args=(-type f ! -path '*/raw/*')
  for ri in "${RECORDED_INPUTS[@]}"; do
    find_args+=(! -path "$SCRATCH/$ri")
  done
  find "$SCRATCH/$lec/outputs" "${find_args[@]}" -delete
  env -i HOME="$HOME" PATH="$HOME/.local/bin:/usr/bin:/bin" \
    UV_PROJECT_ENVIRONMENT="$ROOT/.venv" \
    bash "$SCRATCH/$lec/run_repo.sh" > "$SCRATCH/$lec.log" 2>&1
  status=$?
  diff -r -x raw "$lec/outputs" "$SCRATCH/$lec/outputs" > "$SCRATCH/$lec.diff"
  /usr/bin/python3 - "$lec" "$SCRATCH/$lec.diff" "$SCRATCH/$lec.log" tools/noise.txt "$status" <<'PYEOF' >> "$REPORT"
import pathlib
import re
import sys

lec, diff_path, log_path, noise_path, status_arg = sys.argv[1:6]

diff_text = pathlib.Path(diff_path).read_text()
log_text = pathlib.Path(log_path).read_text()

# skip lines of the exact form: skipped <script>: <reason> (outputs: <file> [<file> ...])
skip_files = {}
for line in log_text.splitlines():
    m = re.match(r"^skipped (.+?): (.+) \(outputs: (.+)\)$", line)
    if m:
        _, reason, files = m.groups()
        for f in files.split():
            skip_files[f] = reason

noise_files = set()
for line in pathlib.Path(noise_path).read_text().splitlines():
    line = line.strip()
    if not line or line.startswith("#"):
        continue
    noise_files.add(line.split()[0])

marker = f"{lec}/outputs"

entries = []
cur = None
for line in diff_text.splitlines():
    m_only = re.match(r"^Only in (.+): (.+)$", line)
    m_diff = re.match(r"^diff -r .* (\S+) (\S+)$", line)
    if m_only:
        if cur:
            entries.append(cur)
        dirpart, fname = m_only.groups()
        idx = dirpart.find(marker)
        rel = dirpart[idx + len(marker):].lstrip("/") if idx != -1 else dirpart
        relpath = f"{rel}/{fname}" if rel else fname
        cur = {"relpath": relpath, "lines": [line]}
    elif m_diff:
        if cur:
            entries.append(cur)
        leftpath = m_diff.group(1)
        idx = leftpath.find(marker)
        relpath = leftpath[idx + len(marker):].lstrip("/") if idx != -1 else leftpath
        cur = {"relpath": relpath, "lines": [line]}
    else:
        if cur is not None:
            cur["lines"].append(line)
if cur:
    entries.append(cur)

output_lines = []
other_present = False
noise_present = []
for e in entries:
    rel = e["relpath"]
    if rel in skip_files:
        output_lines.append(f"{lec}: not rerun: {rel}: {skip_files[rel]}")
    elif f"{lec}/outputs/{rel}" in noise_files:
        noise_present.append(rel)
        output_lines.extend(e["lines"])
    else:
        other_present = True
        output_lines.extend(e["lines"])

if other_present:
    word = "DIFFER"
elif noise_present:
    word = "identical except noise: " + ", ".join(noise_present)
else:
    word = "identical"

print(f"{lec}: runner exit {status_arg}, outputs {word}")
for l in output_lines:
    print(l)
PYEOF
  grep '^skipped ' "$SCRATCH/$lec.log" >> "$REPORT" || true
done
cat "$REPORT"
