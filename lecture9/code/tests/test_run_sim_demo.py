"""run_sim_demo.sh (L9): a trial file that still holds the UNSET_ placeholders is refused
before anything runs. DOCKER=false and a temporary HOME, so a check that fails to refuse
cannot reach the container or write real logs.

config/l9_trial.yaml has START_TIME and DURATION set from the dry run, so the refusal
tests write a template with the placeholders to a temporary folder."""
import os
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
TEMPLATE = """ID: LEC90001
CHALLENGES:
  VOLTAGE_TESTER_MALFUNCTIONS:
    - START_TIME: UNSET_START_TIME
      DURATION: UNSET_DURATION
      TESTER: 1
"""


def wrapper(tmp_path, *args):
    env = {"PATH": "/usr/bin:/bin", "HOME": str(tmp_path), "DOCKER": "false",
           "DEMO_LECTURES": str(tmp_path / "lectures"), "DEMO_LOGS": str(tmp_path / "logs"),
           "SKILLS_REPO": str(tmp_path / "no_skills_repo")}
    return subprocess.run(["bash", str(HERE / "run_sim_demo.sh"), *args], cwd=tmp_path, env=env,
                          capture_output=True, text=True)


def template(tmp_path):
    """A trial file with the placeholders, in tmp_path/trial."""
    (tmp_path / "trial").mkdir()
    path = tmp_path / "trial" / "l9_trial.yaml"
    path.write_text(TEMPLATE)
    return path


def test_a_trial_file_with_unset_placeholders_is_refused(tmp_path):
    # a relative path is read from the wrapper's folder
    rel = os.path.relpath(template(tmp_path), HERE)
    r = wrapper(tmp_path, "--name", "x", "--sim", rel, "config/l9_user_config.yaml",
                "3600", "--", "closed_loop.py", "--policy", "wait")
    assert r.returncode == 2
    assert r.stderr == (f"run_sim_demo: {rel} still holds UNSET_ placeholders; "
                        "set START_TIME and DURATION first, from the dry run's cycle times\n")
    assert sorted(os.listdir(tmp_path)) == ["trial"]   # nothing written


def test_a_trial_file_without_placeholders_reaches_the_l8_script(tmp_path):
    # no --name, so the L8 script stops at its usage check, before any docker call
    for trial in ("config/l9_trial_dry.yaml", "config/l9_trial.yaml"):
        r = wrapper(tmp_path, "--sim", trial, "config/l9_user_config.yaml", "3600",
                    "--", "closed_loop.py", "--policy", "replan")
        assert r.returncode == 2 and r.stderr == "run_sim_demo: usage: see the comment at the top\n"


def test_an_absolute_trial_path_is_checked_too(tmp_path):
    r = wrapper(tmp_path, "--name", "x", "--sim", str(template(tmp_path)),
                "config/l9_user_config.yaml", "3600", "--", "closed_loop.py", "--policy", "wait")
    assert r.returncode == 2 and "still holds UNSET_ placeholders" in r.stderr
