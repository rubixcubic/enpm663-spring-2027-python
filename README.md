# ENPM663 Spring 2027: lecture scripts

ENPM663, "Agentic Physical AI for Manufacturing Robotics," is a course on
agentic robotics built around ARIAC, a NIST manufacturing simulation. This
repository holds the lecture scripts that run without ROS 2, for lectures 2 to
13. Each `lectureN/` folder has the scripts in `code/` and the measured
outputs the slides quote in `outputs/`. Lecture 1's scripts all talk to ROS 2,
so it has no folder here.

The scripts that need ROS 2, or the ARIAC simulation, are not in this
repository. They are in the course's slides repository and on each lecture's
docs code page (see "What is not here" below).

## Setup

Install [uv](https://docs.astral.sh/uv/), then clone and sync this
repository:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
git clone <url> enpm663-spring-2027-python
cd enpm663-spring-2027-python
uv sync
```

`uv sync` installs Python 3.12 and every pinned package (NumPy, PyYAML,
py_trees, jsonschema, the Unified Planning Framework and its Fast Downward
engine, google-genai, httpx, Pillow) into a `.venv` folder, plus pytest for
the tests under `tools/`.

### Run with ROS 2 not sourced

Run every command in this README from a terminal where ROS 2 is **not**
sourced. If a terminal has sourced ROS 2 Jazzy, `/opt/ros/jazzy` (and any
sourced workspace) goes onto `PYTHONPATH` ahead of this project's `uv`
environment, so ROS's own package versions shadow the pinned ones. With ROS 2
sourced, `pytest` fails while it loads ROS's `launch_pytest` plugin, with
`No module named 'lark'`. If you must run a command from a terminal that has
ROS 2 sourced, prefix it with `env -u PYTHONPATH`.

## Running a lecture's scripts

Run one script from its own `code/` folder:

```bash
cd lecture2/code
uv run python toy_factory.py
```

To rerun a whole lecture and rewrite its `outputs/` folder, run its
`run_repo.sh` from the repository root:

```bash
bash lecture2/run_repo.sh
```

Some lectures also have a `code/run_all.sh`. That script is the slides
repository's own runner: it uses the system Python, and in some lectures
ROS 2. It is not for students; use `run_repo.sh` instead.

The files in `outputs/` are what the lecture slides quote. Rerunning a
lecture with `run_repo.sh` reproduces every output it writes byte for byte,
except the files listed in `tools/noise.txt` (measured times that change from
run to run). A step that `run_repo.sh` cannot run here prints a `skipped ...`
line and leaves that step's committed outputs in place. Lecture 13's outputs
were measured under jsonschema 4.26.0; its other outputs are identical under
this project's jsonschema 4.10.3, so only its `versions.txt` is skipped.

## Running a lecture's tests

Lectures 8, 9 and 13 have pytest tests in `code/tests/`. `run_repo.sh` does
not run them. Run them from the lecture's `code/` folder, with
`python -m pytest`:

```bash
cd lecture8/code
uv run python -m pytest tests
```

`python -m pytest` puts the `code/` folder on Python's import path, and the
tests need it there. `uv run pytest tests` in `code/`, or
`uv run pytest lecture8/code/tests` from the repository root, stops with 4
errors while it collects lecture 8's tests.

## Which scripts call the Gemini API

No `run_repo.sh` step calls the Gemini API. A script calls it only when you
run one of its live modes by hand. Each live mode reads a key file:

| Lecture | Live mode you run by hand | Key file it reads | It also needs |
|---|---|---|---|
| L8 | `orchestrator.py --fake` (Run 1, the default `--runs 1`) | `$GEMINI_KEY_FILE`, or `/dev/shm/enpm663_gemini_key` when that variable is not set | `DEMO_RAW_DIR` set |
| L8 | `orchestrator.py` without `--fake` | the same | ROS 2 and ARIAC |
| L8 | `structured_live.py` | `$GEMINI_KEY_FILE` | `DEMO_RAW_DIR` set |
| L8 | `gemini_model.py --probe OUT_DIR` | `$GEMINI_KEY_FILE` | nothing else |
| L9 | `closed_loop.py --policy replan` or `--policy wait`, without `--scripted` | `$GEMINI_KEY_FILE`, or `/dev/shm/enpm663_gemini_key` when that variable is not set | ROS 2 and ARIAC |
| L13 | `er_demo.py --live KEY_FILE RAW_DIR IMAGE.png ...`, or `--live-structured` | the `KEY_FILE` you pass | nothing else |
| L13 | `er_rerun.py NAME FROM` | `~/.config/enpm663/gemini_key` | a recorded session in `outputs/raw/FROM` |
| L13 | `er_session.py TRIAL USER_CONFIG N` | `$GEMINI_KEY_FILE`; with it not set, it saves the images and calls no model | ARIAC, in the skills container (through `run_er_session.sh`) |

`orchestrator.py` and `closed_loop.py` run the scripted model instead when the
key file does not exist. When it does exist, `orchestrator.py --fake` calls
Gemini; run `orchestrator.py --fake --runs dry` or `--runs 2` for the
scripted model.

## Lectures

| Lecture | Title | Scripts here | Key file for a live mode |
|---|---|---|---|
| L2 | System Architectures for Agentic Robotics | 1 | none: no live mode |
| L3 | Knowledge Representation for Agentic Robotics | 3 | none: no live mode |
| L4 | Behavior Trees for Task Execution | 5 | none: no live mode |
| L5 | Sensing and Perception for Robotic Systems | 9 | none: no live mode |
| L6 | Task-Level Planning with PDDL | 8 | none: no live mode |
| L7 | Plan Execution Patterns with Behavior Trees | 7 | none: no live mode |
| L8 | LLM Agents I: Agent Loops, Tool Use, and Structured Output | 17 | `$GEMINI_KEY_FILE` or `/dev/shm/enpm663_gemini_key` |
| L9 | LLM Agents II: VLM Grounding and Agentic Replanning | 4 | `$GEMINI_KEY_FILE` or `/dev/shm/enpm663_gemini_key` |
| L10 | Frames, Transforms, and Motion Planning | 2 | none: no live mode |
| L11 | Recovery, Robustness, and Failure Handling for Agentic Systems | 4 | none: no live mode |
| L12 | Evaluation and Measurement Science for Agentic Systems | 4 | none: no live mode |
| L13 | The Physical AI Frontier: VLAs, Robot Foundation Models, and World Models | 10 | `~/.config/enpm663/gemini_key`, `$GEMINI_KEY_FILE`, or the `KEY_FILE` you pass |

"Scripts here" counts every managed file `tools/classify.py` found for that
lecture, including its test files. A managed file is one that
`tools/sync_course.py` keeps identical here and in the course's slides and
docs repositories (the slides repository only, for a file the docs do not
carry). "Key file for a live mode" names the key files the lecture's live
modes read (see "Which scripts call the Gemini API" above); no `run_repo.sh`
step reads them. See `lectureN/README.md` for what each one shows.

## What is not here, and why

Everything below is a `tools/classification.txt` verdict or a `skipped ...`
line that `lectureN/run_repo.sh` prints; see those files for the exact
wording.

- **The ROS 2 scripts.** Lecture 1's four scripts, and one or more scripts in
  lectures 4, 5, 8 and 10 (`ros_tree_demo.py`, `pc2_roundtrip.py`,
  `stop_test.py`, `tf_agv_moves.py`, `tf_failures.py`, `pixel_to_table.py`)
  import or call ROS 2 at some point. They are in the slides repository and
  on each lecture's docs code page.
- **L8's `skills_mcp_client.py` and `skills_mcp_server.py`.** Excluded: they
  need the `mcp` package, which needs `jsonschema>=4.20`, and this project
  pins `jsonschema==4.10.3`.
- **L9's `tests/test_run_sim_demo.py`.** It tests `run_sim_demo.sh`, which
  needs ARIAC and Docker, so it is not in this repository.
- **Outputs that need what this repository cannot carry.** Raw camera images
  and API responses (several recorded runs in lectures 8, 9 and 13), and an
  ARIAC source checkout (lecture 5's `mesh_depths.py`). `run_repo.sh` prints a
  `skipped ...` line for each such step instead of running it.
- **Several lectures' `versions.txt` is skipped, each for its own reason.**
  - Lecture 4 needs `py_trees_ros`, a ROS package.
  - Lectures 5 and 10 report the ROS 2 distribution.
  - Lecture 7 needs ROS 2, `g++` and BehaviorTree.CPP.
  - Lecture 11 sources ROS 2 to report the versions of the `py_trees` and
    `jsonschema` packages that ROS ships.
  - Lectures 8 and 9 query the course's Docker container
    (`enpm663_skills_dev`).
  - Lecture 6 compares two Pythons that are the same uv environment here, so
    `run_repo.sh` does not rerun that comparison.
  A few other steps are skipped for their own reasons (two shell test
  scripts, the deck's own `.tex` file for a listings check in lectures 8 and
  9); `run_repo.sh` names each one.

## For maintainers

This repository is the master copy of the lecture scripts. Start by checking
that the copies in the slides and docs repositories agree with this
repository:

```bash
uv run python tools/sync_course.py --check
```

(prefix each command with `env -u PYTHONPATH` if your terminal has ROS 2
sourced). It lists each copy that differs or is missing, then prints
`N problem(s)`. Edit a script here, then copy it into the slides and docs
repositories:

```bash
uv run python tools/sync_course.py --write
```

`--write` copies nothing when a copy that differs is newer than this
repository's file: it lists each such copy and exits 1. `--write --force`
overwrites them anyway. Then rebuild the lecture's deck and docs page. Before
you commit, run `--check` again. It must print `0 problem(s)`.

Some outputs can only be regenerated in the slides repository, because they
need ROS 2 or the course's Docker container (for example the `versions.txt`
files of lectures 4, 5, 7, 8, 9, 10 and 11). To bring such a file back, copy
it by hand from the slides repository to the same path here, with a plain
`cp`, then run `--check`.

To rerun every lecture and refresh `tools/run_report.txt`:

```bash
bash tools/run_all_lectures.sh
```

`tools/classify.py` regenerates the code part of `tools/manifest.toml` (which
scripts import without ROS 2, and which files go to the slides repository,
the docs repository, or both) by reading every script's imports. It does not
generate the `outputs/` entries or the `code/run_all.sh` entries: those were
added by hand, after checking which outputs a managed script writes. A rerun
reads the existing `tools/manifest.toml` and keeps each of those entries in
the list it was in. Run it from a clean environment:

```bash
env -i HOME=$HOME PATH=$HOME/.local/bin:/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 uv run python tools/classify.py
```

## Pushing (for the instructor)

This repository has no remote yet. To add one and push:

```bash
git remote add origin <url>
git config user.email
git push -u origin main
```

Check the email `git config user.email` prints against the account that owns
the remote before you push: `zeidk@umd.edu` for a `rubixcubic` remote,
`zeid.kootbally@gmail.com` for a `zeidk` remote.
