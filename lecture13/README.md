# Lecture 13 scripts

Ten managed files. They show the final demo's embodied-reasoning step. Each
one imports without ROS 2, but `er_session.py` uses ROS 2 and ARIAC when it
runs, so here only its tests run. `run_repo.sh` runs `er_demo.py` and
`score_er.py` in their offline, scripted mode (no API key, no network). Their live modes, which you
run by hand, and the key file each one reads are listed in the root README's
"Which scripts call the Gemini API" section.

A managed file is one that `tools/sync_course.py` keeps identical here and in
the course's slides and docs repositories (the slides repository only, for a
file the docs do not carry).

- **`er_demo.py`**: offline, builds the request, sends it 12 times through
  the stand-in, and checks each answer against the schema; live, sends your
  images to the model and saves every request and response. Slide:
  "lecture13/code/er_demo.py (excerpt)". Writes `outputs/er_demo.txt`
  (offline run).
- **`score_er.py`**: precision and recall per defect type: for the scripted
  example (`--scripted`), or for a recorded run against ARIAC's cell log.
  Slide: "lecture13/code/score_er.py (excerpt)". Writes `outputs/score_er.txt`
  (scripted). Its recorded-run outputs, `outputs/score_er_rec1.txt` and
  `outputs/score_er_rec2.txt`, need `outputs/raw/er_rec1` and
  `outputs/raw/er_rec2`, which are never committed, so `run_repo.sh` skips
  those two runs here.
- **`er_rerun.py`**: Run 2: sends a recorded session's 12 images again, with
  structured output, 13 seconds apart. Not shown on a slide. Writes
  `outputs/er_rec2.txt` and `outputs/raw/er_rec2/`; needs a live key and a
  recorded session's images, so `run_repo.sh` does not run it here.
- **`er_session.py`**: the L13 live run: real ARIAC camera images of 12
  cells, then one model call per image. It runs inside the skills container,
  through the slides repository's `run_er_session.sh`, so `run_repo.sh` does
  not run it here. Not described on the docs code page. Not shown on a slide.
- **`listings_l13.py`**: cuts the L13 slide listings out of `outputs/`, and
  checks that each deck listing matches its file. Not described on the docs
  code page. Not shown on a slide. Its `build` step writes the seven files in
  `outputs/listings/`. Four of them (`run1_answers.txt`, `run2_table.txt`,
  `run2_rates.txt`, `run2_cost.txt`) are cut from `outputs/score_er_rec1.txt`
  and `outputs/score_er_rec2.txt`. When those two files are missing,
  `run_repo.sh` builds only the other three and prints a `skipped ...` line
  for the four.
- **`tests/conftest.py`**: puts `lecture13/code`, L8's code and L9's code on
  the import path for the L13 tests. Not described on the docs code page. Not
  shown on a slide. Pytest setup, not a test module itself.
- **`tests/stop_child.py`**: a demo that starts a child process the way
  `er_session.py` starts ARIAC, for `check_stops_in_container.sh`. That
  shell script is in the slides repository, not here. Not described on the
  docs code page. Not shown on a slide.
- **`tests/test_er_demo.py`**: `er_demo.py`: the offline stand-in, and the
  live client against a mock server, with no key and no network. Not
  described on the docs code page. Not shown on a slide. Pytest tests;
  `run_repo.sh` does not run them here (run them with `cd lecture13/code &&
  env -u PYTHONPATH uv run python -m pytest tests`).
- **`tests/test_er_session.py`**: `er_session.py`: the cell log parser, the
  capture timing and the capture loop, without ROS 2. Not described on the
  docs code page. Not shown on a slide. Pytest tests; see above for how to
  run them.
- **`tests/test_score_er.py`**: `score_er.py`: the interval arithmetic, set
  labels, the camera model and a whole fake recording. Not described on the
  docs code page. Not shown on a slide. Pytest tests; see above for how to
  run them.
