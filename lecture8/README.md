# Lecture 8 scripts

Seventeen managed files: the L8 code that needs no ROS 2 to import, plus
its tests. Most of it runs with no ARIAC and no API key; `sim_session.py`
and `smoke.py` need ARIAC when they run. The scripts that only run against
ARIAC, with Gemini or with the MCP server, are not exercised by this
repository's `run_repo.sh`; see the root README's "What is not here" section.

A managed file is one that `tools/sync_course.py` keeps identical here and in
the course's slides and docs repositories (the slides repository only, for a
file the docs do not carry).

- **`orchestrator.py`**: the agent loop: observe, ask the model, check the
  call (`check_call()` and `guard()`), run it, record the result, stop. Run 1
  uses Gemini, Run 2 a scripted model. Slide: "lecture8/code/orchestrator.py,
  guard() (two excerpts)". Its recorded output, `outputs/agent_rec1.txt`, was
  made against ARIAC and is not reproduced by `run_repo.sh` here.
- **`skill_tools.py`**: the ten tools: the seven skill actions of the two
  inspection robots and three ARIAC readings, each a declaration (name,
  description, schema) and a method of `SkillTools`. Slide:
  "lecture8/code/skill_tools.py (excerpt)". No output file of its own;
  imported by `orchestrator.py` and `fake_tools.py`.
- **`fake_tools.py`**: `FakeTools`: a factory with no ARIAC, with the same
  tool names, arguments and result shapes. Every value in it is chosen for
  this example. Not shown on a slide. No output file of its own; imported by
  `orchestrator.py`'s `--fake` mode.
- **`gemini_model.py`**: `GeminiModel`: the Gemini client, with the same call
  as `ScriptedModel`. It reads the key from a file and saves every API
  response. Not shown on a slide. No output file here; it is used only
  against ARIAC or with a key.
- **`gemini_prices.py`**: the model name and its prices, quoted from the
  Gemini pricing page with the date read. Slide: "The Arithmetic, at the
  Prices of gemini_prices.py". No output file of its own; imported by
  `token_growth.py`.
- **`sim_session.py`**: waits for ARIAC and the skills, starts the
  competition, and stops a demo that runs too long. Not shown on a slide. No
  output file; used only against ARIAC.
- **`stub_agv.py`**: a stand-in for ARIAC's `/agvN/move` action and the stub
  factory of the Structured Output section. Not shown on a slide. No output
  file of its own; imported by `validator.py`.
- **`validator.py`**: parse, schema and semantic checks on seven scripted
  outputs, then two runs of a bounded retry. Slide:
  "lecture8/code/validator.py (excerpt)". Writes `outputs/validator.txt`.
- **`structured_live.py`**: one real Gemini output, run through
  `validator.check()`. Slide: "Output of lecture8/code/structured_live.py".
  Its recorded output, `outputs/structured_live.txt`, needs ARIAC and a key
  and is not reproduced by `run_repo.sh` here; `run_repo.sh` instead imports
  its `SYSTEM` message and writes it to `outputs/system_message.txt`.
- **`run_cost.py`**: reads Run 1's raw API responses and writes the cost
  table of the slides and `agent_run1_usage.json`. Slide: "Output of
  lecture8/code/run_cost.py, from Run 1's Raw API Responses". Its outputs,
  `outputs/agent_run1_cost.txt` and `outputs/agent_run1_usage.json`, are
  recorded from raw responses this repository does not carry, so
  `run_repo.sh` does not rerun it.
- **`token_growth.py`**: input tokens and cost of a ReAct run and of
  plan-and-execute, for 5, 10, 20 and 40 steps, from Run 1's measured tokens.
  Slide: "Output of lecture8/code/token_growth.py". Writes
  `outputs/token_growth.txt`.
- **`listings.py`**: cuts the slide listings out of the outputs, and checks
  that every listing on a slide matches its output file byte for byte. Not
  shown on a slide. Writes `outputs/listings/*.txt` when it builds; its
  `check` step needs the deck's `L8-ENPM663-v1.0.tex`, which lives in the
  slides repository, so `run_repo.sh` skips that step here.
- **`smoke.py`**: the smoke test before any recording: each act tool once,
  with its result code checked, in two cycles. It needs ARIAC and the skills
  (it calls `ros_node()` in `main()`). Not described on the docs code page.
  Not shown on a slide.
- **`tests/test_gemini_model.py`**: `gemini_model.py` against three recorded
  responses (`tests/fixtures`), and the key rules. Not described on the docs
  code page. Not shown on a slide. Pytest tests; `run_repo.sh` does not run
  them here (run them with `cd lecture8/code && env -u PYTHONPATH uv run
  python -m pytest tests`).
- **`tests/test_listings.py`**: `listings.py`: the filter, and the
  byte-for-byte check of every deck listing. Not described on the docs code
  page. Not shown on a slide. Pytest tests; see above for how to run them.
- **`tests/test_orchestrator.py`**: the orchestrator loop with
  `ScriptedModel` and `FakeTools`: stop conditions, checks, record. Not
  described on the docs code page. Not shown on a slide. Pytest tests; see
  above for how to run them.
- **`tests/test_skill_tools.py`**: tool declarations against their Python
  methods, and the pure helpers, with no ROS 2. Not described on the docs
  code page. Not shown on a slide. Pytest tests; see above for how to run
  them.
