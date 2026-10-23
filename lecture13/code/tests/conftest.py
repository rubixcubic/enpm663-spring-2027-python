"""The L13 tests import lecture13/code and L8's gemini_model (_with_deadline, read_key)
and L9's vlm_check (to_png), as er_session.py does in the container."""
import sys
from pathlib import Path

CODE = Path(__file__).resolve().parents[1]
for p in (CODE, CODE.parents[1] / "lecture8" / "code", CODE.parents[1] / "lecture9" / "code"):
    sys.path.insert(0, str(p))
