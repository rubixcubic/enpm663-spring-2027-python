#!/usr/bin/env bash
# Rerun this lecture's scripts that need no ROS 2, in the uv environment, and rewrite outputs/.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$(dirname "$0")/code"
PY=(uv run --project "$ROOT" --quiet python)

"${PY[@]}" -c \
  "import sys; from importlib.metadata import version; print('Python', sys.version.split()[0], 'jsonschema', version('jsonschema'))" \
  > ../outputs/versions.txt
(cd ../outputs && "${PY[@]}" ../code/kit_views.py > kit_views.txt 2>&1)
"${PY[@]}" ontology_check.py > ../outputs/ontology_check.txt 2>&1
"${PY[@]}" track_cell.py > ../outputs/track_cell.txt 2>&1
