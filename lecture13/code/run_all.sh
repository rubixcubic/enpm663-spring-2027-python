#!/usr/bin/env bash
# Runs every offline L13 part and writes its output to ../outputs/.
# google-genai is not installed for the system Python, so the examples
# run in a venv (VENV, default below) with google-genai and jsonschema.
# env -i drops this shell's ROS and Python paths. No network and no key:
# - er_demo.txt and score_er.txt: the scripted stand-in (see er_demo.py);
# - score_er_rec1.txt and score_er_rec2.txt: the two recorded runs, scored
#   from their files in ../outputs/raw/ (Run 1 recorded once by
#   run_er_session.sh, Run 2 once by er_rerun.py on Run 1's images);
# - listings/: the slide listings, cut from these files (listings_l13.py).
# The live runs need the key (and Run 1 ARIAC): run_er_session.sh, er_rerun.py.
set -euo pipefail
cd "$(dirname "$0")"
VENV="${VENV:-$HOME/l13-venv}"
PY="$VENV/bin/python"
E=(env -i HOME="$HOME" PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1)
"${E[@]}" "$PY" -c \
  "import sys; from importlib.metadata import version as v; print('Python', sys.version.split()[0], 'google-genai', v('google-genai'), 'httpx', v('httpx'), 'jsonschema', v('jsonschema'))" \
  > ../outputs/versions.txt
"${E[@]}" "$PY" er_demo.py > ../outputs/er_demo.txt 2>&1
"${E[@]}" "$PY" score_er.py --scripted > ../outputs/score_er.txt 2>&1
for rec in er_rec1 er_rec2; do
  if [[ -d ../outputs/raw/$rec ]]; then
    "${E[@]}" "$PY" score_er.py ../outputs/raw/$rec > ../outputs/score_$rec.txt 2>&1
  fi
done
if [[ -f listings_l13.json ]]; then   # the slides repo only
  "${E[@]}" "$PY" listings_l13.py build listings_l13.json
fi
if [[ -d tests ]]; then   # the slides repo only
  "${E[@]}" "$PY" -m pytest -q -p no:cacheprovider tests
  bash tests/test_run_er_session.sh
fi
cat ../outputs/versions.txt ../outputs/er_demo.txt ../outputs/score_er.txt
