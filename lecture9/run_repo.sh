#!/usr/bin/env bash
# Rerun this lecture's scripts that need no ROS 2, in the uv environment, and rewrite outputs/.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$(dirname "$0")/code"
PY=(uv run --project "$ROOT" --quiet python)
OUT=../outputs

# write OUTPUT_FILE from a command: to a .tmp file first, moved into place only on
# success, so a failed run keeps the last good output and set -e stops the script
write() {
  local file=$1; shift
  "${PY[@]}" "$@" > "$file.tmp" 2>&1 || { cat "$file.tmp" >&2; rm -f "$file.tmp"; return 1; }
  mv "$file.tmp" "$file"
}

echo "skipped versions.txt: needs docker exec into enpm663_skills_dev (outputs: versions.txt)"

write $OUT/vlm_check.txt vlm_check.py

"${PY[@]}" ../../lecture8/code/listings.py build listings_l9.json
if [[ -f ../L9-ENPM663-v1.0.tex ]]; then
  "${PY[@]}" ../../lecture8/code/listings.py check ../L9-ENPM663-v1.0.tex $OUT/listings
else
  echo "skipped listings.py check: needs the deck's L9-ENPM663-v1.0.tex, not in this repo"
fi

echo "skipped pytest tests: run separately in Step 5"
