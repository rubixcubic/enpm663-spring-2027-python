# Lecture 13 scripts

Ten managed files. They show the final demo's embodied-reasoning step. None
of them uses ROS 2 or the ARIAC simulation. `run_repo.sh` runs them in their
offline, scripted mode (no API key, no network); a live run needs
`ENPM663_LIVE=1` and a key file, as the root README explains.

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
- **`er_session.py`**: not described on the docs code page. Not shown on a
  slide.
- **`listings_l13.py`**: not described on the docs code page. Not shown on a
  slide. When it builds, it writes `outputs/listings/run1_answers.txt`,
  `outputs/listings/run2_table.txt`, `outputs/listings/run2_rates.txt` and
  `outputs/listings/run2_cost.txt`; these need
  `outputs/score_er_rec1.txt`/`outputs/score_er_rec2.txt`, which need
  `outputs/raw/`, never committed, so `run_repo.sh` skips this step here.
- **`tests/conftest.py`**: not described on the docs code page. Not shown on
  a slide. Pytest fixtures, not a test module itself.
- **`tests/stop_child.py`**: not described on the docs code page. Not shown
  on a slide.
- **`tests/test_er_demo.py`**: not described on the docs code page. Not
  shown on a slide. Pytest tests; `run_repo.sh` does not run them here (run
  them with `cd lecture13/code && env -u PYTHONPATH uv run python -m
  pytest`).
- **`tests/test_er_session.py`**: not described on the docs code page. Not
  shown on a slide. Pytest tests; see above for how to run them.
- **`tests/test_score_er.py`**: not described on the docs code page. Not
  shown on a slide. Pytest tests; see above for how to run them.
