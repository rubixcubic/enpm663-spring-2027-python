# Lecture 9 scripts

Three managed files. They build on the L8 code, so keep `lecture9/code/` next
to `lecture8/code/`.

- **`vlm_check.py`**: the prompts, the schema, `check()` and `cross_check()`.
  Run on its own, it plays the scripted run: a weak prompt, a structured
  prompt with one re-prompt, and a cross-check before a high-priority
  submit. `live()` is the live check that `closed_loop.py` calls. Slide:
  "lecture9/code/vlm_check.py (excerpt)". Writes `outputs/vlm_check.txt`.
- **`closed_loop.py`**: Gemini, through the L8 orchestrator, fills agv1's
  four slots while voltage tester 1 malfunctions, under a replan or a wait
  policy, then prints the kit total. Slide: "lecture9/code/closed_loop.py
  (excerpt)". Its recorded outputs, `outputs/closed_loop_replan_rec1.txt`
  and `outputs/closed_loop_wait_rec1.txt`, need ARIAC and a key and are not
  reproduced by `run_repo.sh` here.
- **`tests/test_vlm_check.py`**: not described on the docs code page. Not
  shown on a slide. Pytest tests; `run_repo.sh` does not run them here (run
  them with `cd lecture9/code && env -u PYTHONPATH uv run python -m
  pytest`).
