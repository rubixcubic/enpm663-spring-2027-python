# Lecture 11 scripts

Four managed scripts. None of them needs a simulator or a model: each runs in
plain Python and prints a trace.

A managed file is one that `tools/sync_course.py` keeps identical here and in
the course's slides and docs repositories (the slides repository only, for a
file the docs do not carry).

- **`recovery_tree.py`**: a selector, a Retry decorator and a guard, in four
  separate runs with injected failures. Slide:
  "lecture11/code/recovery_tree.py (excerpt)". Writes
  `outputs/recovery_tree.txt`.
- **`timeout_demo.py`**: Timeout turns a skill that hangs into a failure the
  tree can react to. Slide: "lecture11/code/timeout_demo.py (excerpt)".
  Writes `outputs/timeout_demo.txt`.
- **`llm_output_checker.py`**: L8's `check_call()` (tool, schema, guard) on
  scripted replies that use the L8 agent's tools, and the re-prompt once,
  then fall back policy through L8's `run()`. Not shown on a slide. Writes
  `outputs/llm_output_checker.txt`.
- **`tester_watcher.py`**: a voltage tester watcher that treats a
  `MALFUNCTIONING` status and silence both as failure, and the averaging
  worked example. Not shown on a slide. Writes `outputs/tester_watcher.txt`.
