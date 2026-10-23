"""L13 Run 2: ask the model again about the images a session already saved.

  python3 er_rerun.py NAME FROM      e.g.  er_rerun.py er_rec2 er_rec1

No simulation: the 12 PNG files and ARIAC's cell log come from
../outputs/raw/FROM (recorded by run_er_session.sh). Each image is sent once
with er_demo.STRUCTURED (structured output, store=False), calls start
er_demo.GAP_S apart, and nothing else changes from Run 1 (model, prompt,
thinking level, no retry, the deck's schema check on every answer).

Writes ../outputs/NAME.txt (header, the call log, the exit status) and
../outputs/raw/NAME/ (requests with the key and image bytes removed,
responses as received, answers.json, and copies of FROM's captures.json and
cell_info.txt so score_er.py can score NAME). The PNG files are not copied:
each saved request names its image's SHA-256 and the file in FROM.
The key is read from ~/.config/enpm663/gemini_key (mode 600) and never printed.
"""

import hashlib
import json
import shutil
import sys
import time
from datetime import datetime
from importlib.metadata import version
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "lecture8" / "code"))

import er_demo                      # noqa: E402
from gemini_model import read_key   # noqa: E402

KEY_FILE = Path.home() / ".config" / "enpm663" / "gemini_key"


def main(name, source):
    out = HERE.parent / "outputs"
    src, raw = out / "raw" / source, out / "raw" / name
    if (out / f"{name}.txt").exists() or raw.exists():
        sys.exit(f"{name} exists; every recording keeps its own name")
    captures = json.loads((src / "captures.json").read_text())
    raw.mkdir(parents=True)
    for f in ("captures.json", "cell_info.txt"):
        shutil.copyfile(src / f, raw / f)
    images = {c["cell"]: (src / f"{c['cell']}.png").read_bytes() for c in captures}

    log = []

    def say(line):
        log.append(line)
        print(line, flush=True)

    start = datetime.now().astimezone()
    t0 = time.monotonic()
    say(f"images: outputs/raw/{source}/c01.png to c{len(images):02d}.png, "
        f"saved by the {source} session (no simulation in this run)")
    for cell, png in images.items():
        say(f"{cell}.png sha256 {hashlib.sha256(png).hexdigest()}")
    fmt = er_demo.STRUCTURED["response_format"]
    say(f"model calls: {er_demo.MODEL}, one per image, no retry, "
        f"{er_demo.GAP_S} s from one call's start to the next")
    say(f"request adds: response_format type {fmt['type']}, mime_type {fmt['mime_type']}, "
        f"schema er_demo.ANSWER_SCHEMA; store {er_demo.STRUCTURED['store']}")
    key = read_key(KEY_FILE)
    recorder = er_demo.Recorder(raw, key, image_dir=f"../{source}/")
    client = er_demo.make_live_client(key, recorder)
    results = er_demo.ask_live(client, recorder, images, log=say,
                               extra=er_demo.STRUCTURED, gap_s=er_demo.GAP_S)
    answered = sum(r["error"] is None for r in results.values())
    say(f"calls answered: {answered} of {len(images)}")
    wall = time.monotonic() - t0

    models = sorted({m for f in raw.glob("c*.response.json")
                     if (m := json.loads(f.read_text()).get("model"))})
    reported = ", ".join(models) or "none (no API response)"
    head = [
        f"date: {start:%Y-%m-%d %H:%M:%S %Z}",
        f"session: {name} (lecture 13): er_rerun.py {name} {source}, on the host",
        f"model (as the API reports it): {reported}",
        f"Recorded once, on {start:%Y-%m-%d}, with {reported}. A rerun gives different answers.",
        f"venv: Python {sys.version.split()[0]} | google-genai {version('google-genai')} "
        f"| httpx {version('httpx')} | jsonschema {version('jsonschema')}",
        "---",
    ]
    status = 0 if answered == len(images) else 1
    text = "\n".join(head + log + [f"--- exit status {status}, {wall:.0f} wall s"]) + "\n"
    (out / f"{name}.txt").write_text(recorder.clean(text))
    return status


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("usage: er_rerun.py NAME FROM")
    sys.exit(main(sys.argv[1], sys.argv[2]))
