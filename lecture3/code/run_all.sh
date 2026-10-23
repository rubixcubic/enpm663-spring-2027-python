#!/usr/bin/env bash
# Runs every L3 example and writes its output to ../outputs/.
# env -i drops this shell's ROS and Python paths, so the system Python
# and its jsonschema package are the ones used. kit_views.py runs in
# ../outputs/, so the kit_record.json it writes lands there.
set -euo pipefail
cd "$(dirname "$0")"
PY="env -i HOME=$HOME PATH=/usr/bin:/bin /usr/bin/python3"
$PY -c \
  "import sys; from importlib.metadata import version; print('Python', sys.version.split()[0], 'jsonschema', version('jsonschema'))" \
  > ../outputs/versions.txt
(cd ../outputs && $PY ../code/kit_views.py > kit_views.txt 2>&1)
$PY ontology_check.py > ../outputs/ontology_check.txt 2>&1
$PY track_cell.py > ../outputs/track_cell.txt 2>&1
cd ../outputs
cat versions.txt kit_views.txt kit_record.json ontology_check.txt \
  track_cell.txt
