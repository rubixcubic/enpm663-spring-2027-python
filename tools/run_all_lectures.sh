#!/usr/bin/env bash
# Rerun every lecture in a scratch copy with its outputs cleared, and compare with the
# committed outputs. Writes tools/run_report.txt. No ROS 2 setup is sourced.
#
# A step the repo cannot run (needs outputs/raw/, an ARIAC source checkout, the Docker
# container or ROS) prints a line of the exact form
#   skipped <script>: <reason> (outputs: <file> [<file> ...])
# The Python block below reads that line from the run's log, drops the matching
# "Only in ...: <file>" line from the diff, and reports "<lecture>: not rerun: <file>:
# <reason>" instead. A file whose content varies run to run (not because a step was
# skipped) is listed once in tools/noise.txt; if every file still differing after that
# is in tools/noise.txt, the lecture is reported "identical except noise", with the
# noise diff lines kept below that line. The lecture is DIFFER when anything else
# differs, when an "Only in" line is left after the skip lines are matched (a missing
# or extra output, even one listed in tools/noise.txt), or when run_repo.sh exits with
# a status other than 0. A "Binary files ... differ" line is a difference of its own.
# The report writes the scratch folder as <scratch> and any other mktemp folder under
# /tmp as <tmp>, and lists the lectures in numeric order, so two runs differ only in
# the noise lines.
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
mapfile -t LECTURES < <(printf '%s\n' lecture*/ | sed 's:/$::' | sort -V)
for lec in "${LECTURES[@]}"; do /bin/cp -r "$lec" "$SCRATCH/"; done
/bin/cp pyproject.toml uv.lock .python-version "$SCRATCH/"
for lec in "${LECTURES[@]}"; do
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
  /usr/bin/python3 - "$lec" "$SCRATCH/$lec.diff" "$SCRATCH/$lec.log" tools/noise.txt "$status" "$SCRATCH" <<'PYEOF' >> "$REPORT"
import pathlib
import re
import sys

lec, diff_path, log_path, noise_path, status_arg, scratch = sys.argv[1:7]

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


def rel_of(path):
    idx = path.find(marker)
    return path[idx + len(marker):].lstrip("/") if idx != -1 else path


entries = []
cur = None
for line in diff_text.splitlines():
    m_only = re.match(r"^Only in (.+): (.+)$", line)
    m_diff = re.match(r"^diff -r .* (\S+) (\S+)$", line)
    m_bin = re.match(r"^Binary files (\S+) and (\S+) differ$", line)
    if m_only or m_diff or m_bin:
        if cur:
            entries.append(cur)
    if m_only:
        dirpart, fname = m_only.groups()
        rel = rel_of(dirpart)
        cur = {"relpath": f"{rel}/{fname}" if rel else fname, "lines": [line], "only": True}
    elif m_diff:
        cur = {"relpath": rel_of(m_diff.group(1)), "lines": [line], "only": False}
    elif m_bin:
        cur = {"relpath": rel_of(m_bin.group(1)), "lines": [line], "only": False}
    elif cur is not None:
        cur["lines"].append(line)
if cur:
    entries.append(cur)

output_lines = []
other_present = status_arg != "0"
noise_present = []
for e in entries:
    rel = e["relpath"]
    if e["only"] and rel in skip_files:
        output_lines.append(f"{lec}: not rerun: {rel}: {skip_files[rel]}")
    elif not e["only"] and f"{lec}/outputs/{rel}" in noise_files:
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
for line in output_lines:
    line = line.replace(scratch, "<scratch>")
    print(re.sub(r"/tmp/tmp\.[A-Za-z0-9]{10}", "<tmp>", line))
PYEOF
  grep '^skipped ' "$SCRATCH/$lec.log" >> "$REPORT" || true
done
cat "$REPORT"
