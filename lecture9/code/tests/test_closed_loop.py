"""closed_loop.py with FakeTools: both policies, the wait tool, the goal check."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from closed_loop import (DRY_REPLIES, MAX_STEPS, PolicyTools, four_slots, kit_line,  # noqa: E402
                         policy_guard, tool_names)
from fake_tools import FakeTools  # noqa: E402
from orchestrator import Record, ScriptedModel, check_call, run  # noqa: E402
from skill_tools import DECLARATIONS, L9_TOOLS  # noqa: E402


def act(name, **args):
    return {"tool": name, "args": args}


def cycle(tester, slot):
    return [act("robot1_pick_from_conveyor"), act("robot1_place_on_tester", tester=tester),
            act("robot2_pick_from_tester", tester=tester), act("robot2_place_in_slot", agv=1, slot=slot)]


def go(replies, tools, policy):
    """One run as closed_loop.main makes it: the policy's tool list and declarations, and its guard."""
    lines, rec = [], Record()
    stop = run(ScriptedModel(replies), PolicyTools(tools, policy), "goal", four_slots, tool_names(policy),
               max_steps=MAX_STEPS, extra_guard=policy_guard(policy), record=rec, out=lines.append)
    return stop, lines, rec


def test_dry_replies_fill_four_slots():
    stop, _, rec = go(DRY_REPLIES, FakeTools(), "replan")
    assert stop == "goal reached" and sorted(rec.slots) == [(1, 1), (1, 2), (1, 3), (1, 4)]


def test_replan_uses_tester_2_while_tester_1_is_down():
    tools = FakeTools(tester_down={1: (70.0, 400.0)})   # down from the second cycle on (values chosen)
    replies = cycle(1, 1) + [act("robot1_pick_from_conveyor"), act("robot1_place_on_tester", tester=1),
                             act("robot1_place_on_tester", tester=2)] + \
        [act("robot2_pick_from_tester", tester=2), act("robot2_place_in_slot", agv=1, slot=2)] + \
        cycle(2, 3) + cycle(2, 4) + [{"text": "done"}]
    stop, lines, _ = go(replies, tools, "replan")
    assert stop == "goal reached" and any("tester 1 is MALFUNCTIONING" in line for line in lines)


def test_wait_policy_refuses_tester_2_and_waits():
    tools = FakeTools(tester_down={1: (70.0, 130.0)})
    replies = cycle(1, 1) + [act("robot1_pick_from_conveyor"), act("robot1_place_on_tester", tester=2),
                             act("wait", seconds=60)] + [act("robot1_place_on_tester", tester=1),
                                                         act("robot2_pick_from_tester", tester=1),
                                                         act("robot2_place_in_slot", agv=1, slot=2)] + \
        cycle(1, 3) + cycle(1, 4) + [{"text": "done"}]
    stop, lines, _ = go(replies, tools, "wait")
    assert stop == "goal reached"
    # fix round 1, I4: the wait run declares tester 1 only, so the schema refuses tester 2
    # before the policy guard (a backstop, tested below) runs; m4: no tester-2 call ran
    assert any("schema: 2 is greater than the maximum of 1" in line for line in lines)
    assert [c for c in tools.calls if c[1].get("tester") == 2] == []


def test_goal_needs_four_voltage_records():
    tools = FakeTools()
    rec = Record()
    for k in (1, 2, 3, 4):
        tools.tray[1][k - 1] = True
    assert not four_slots(tools.snapshot(), rec)
    rec.slots = {(1, k): 3.6 for k in (1, 2, 3, 4)}
    assert four_slots(tools.snapshot(), rec)


def test_kit_line_shows_the_sum_and_the_window():
    rec = Record()
    rec.slots = {(1, 1): 3.61, (1, 2): 3.55, (1, 3): 3.66, (1, 4): 3.58}
    assert kit_line(rec) == "kit total 14.40 V (3.61 + 3.55 + 3.66 + 3.58); window 14.25 to 14.55 V: inside"


# Added beyond the brief: the guard's edges, the goal on a missing tray reading, the
# kit line's other branches, and main() on FakeTools (no ROS, no key, no API call).

def test_policy_guard_refuses_both_tester_2_tools_only_under_wait():
    wait, replan = policy_guard("wait"), policy_guard("replan")
    snap, rec = FakeTools().snapshot(), Record()
    for name in ("robot1_place_on_tester", "robot2_pick_from_tester"):
        assert wait(name, {"tester": 2}, snap, rec) == "policy wait: this run uses tester 1 only"
        assert wait(name, {"tester": 1}, snap, rec) is None
        assert replan(name, {"tester": 2}, snap, rec) is None
    assert wait("wait", {"seconds": 60}, snap, rec) is None
    assert wait("read_testers", {}, snap, rec) is None


def test_wait_seconds_outside_5_to_60_is_refused_by_the_schema():
    tools = FakeTools()
    stop, lines, _ = go([act("wait", seconds=61), act("wait", seconds=4)], tools, "wait")
    assert stop == "2 invalid outputs in a row" and tools.calls == []
    assert any("schema: 61 is greater than the maximum of 60" in line for line in lines)


def test_a_cell_with_no_reading_stops_the_wait_run_after_two_refusals():
    # tester 1 is down from 30 s (chosen): the cell placed at 20 s to 40 s never reads, and
    # two refused calls in a row end the run (orchestrator.MAX_INVALID)
    tools = FakeTools(tester_down={1: (30.0, 400.0)})
    replies = [act("robot1_pick_from_conveyor"), act("robot1_place_on_tester", tester=1),
               act("robot2_pick_from_tester", tester=1), act("robot2_place_in_slot", agv=1, slot=1),
               act("robot2_place_in_slot", agv=1, slot=1)]
    stop, lines, _ = go(replies, tools, "wait")
    assert stop == "2 invalid outputs in a row"
    assert any("the held cell has no voltage record" in line for line in lines)


def test_goal_is_false_without_a_tray_reading():
    rec = Record()
    rec.slots = {(1, k): 3.6 for k in (1, 2, 3, 4)}
    snap = FakeTools().snapshot()
    snap["agvs"]["1"]["slots"] = "NO_READING"     # skill_tools.SkillTools.read_agv with no message
    assert not four_slots(snap, rec)


def test_goal_is_false_with_a_voltage_outside_the_cell_window():
    tools, rec = FakeTools(), Record()
    tools.tray[1] = [True] * 4
    rec.slots = {(1, 1): 3.6, (1, 2): 3.6, (1, 3): 3.9, (1, 4): 3.6}
    assert not four_slots(tools.snapshot(), rec)


def test_kit_line_outside_the_window_and_with_a_missing_record():
    rec = Record()
    rec.slots = {(1, 1): 3.45, (1, 2): 3.50, (1, 3): 3.55, (1, 4): 3.50}
    assert kit_line(rec) == "kit total 14.00 V (3.45 + 3.50 + 3.55 + 3.50); window 14.25 to 14.55 V: OUTSIDE"
    del rec.slots[(1, 4)]
    assert kit_line(rec) == "kit total: not every slot has a voltage record"


def fake_ros(monkeypatch):
    """main() with FakeTools in place of ARIAC: a stand-in sim_session, SkillTools -> FakeTools."""
    import types

    import skill_tools
    monkeypatch.setitem(sys.modules, "sim_session", types.SimpleNamespace(
        start_watchdog=lambda: None, ros_node=lambda name: object(), prepare=lambda node: None))
    monkeypatch.setattr(skill_tools, "SkillTools", lambda node: FakeTools())


def test_main_without_a_key_runs_the_scripted_model_and_writes_the_record(monkeypatch, tmp_path, capsys):
    import json

    import closed_loop
    fake_ros(monkeypatch)
    monkeypatch.setenv("GEMINI_KEY_FILE", str(tmp_path / "no_key"))
    monkeypatch.setenv("DEMO_OUT_DIR", str(tmp_path))
    closed_loop.main(["--policy", "replan", "--vlm-after"])
    out = capsys.readouterr().out
    assert "no key file at" in out and "the live VLM check is skipped" in out
    assert "=== Closed loop, policy replan (scripted model: fixed replies) ===" in out
    assert "Gemini" not in out
    assert "stop: goal reached" in out
    assert "kit total 14.40 V (3.61 + 3.55 + 3.66 + 3.58); window 14.25 to 14.55 V: inside" in out
    assert json.loads((tmp_path / "record.json").read_text()) == {
        "slots": {"1": 3.61, "2": 3.55, "3": 3.66, "4": 3.58}}
    assert not (tmp_path / "vlm_tray.png").exists()


def test_main_refuses_the_live_vlm_check_with_the_scripted_model(monkeypatch, capsys):
    import pytest

    import closed_loop
    with pytest.raises(SystemExit) as stop:
        closed_loop.main(["--policy", "wait", "--scripted", "--vlm-after"])
    assert stop.value.code == 2 and "--vlm-after calls Gemini" in capsys.readouterr().err


def test_the_goal_names_the_policy_line():
    from closed_loop import GOAL, POLICY
    assert GOAL.startswith("Fill all four slots of agv1")
    assert "tester 1 only" in POLICY["wait"] and "wait" in POLICY["wait"]
    assert POLICY["replan"] == "Either tester may be used."


# Fix round 1 (I2, I4, m5): each run's own tools, the first-cell image, the model-error stop.

def test_each_run_offers_only_its_own_tools():
    assert tool_names("replan") == [n for n in L9_TOOLS if n != "wait"]
    assert tool_names("wait") == L9_TOOLS
    replan = PolicyTools(FakeTools(), "replan").declarations(tool_names("replan"))
    wait = PolicyTools(FakeTools(), "wait").declarations(tool_names("wait"))
    assert [d["name"] for d in replan] == tool_names("replan")
    assert [d["name"] for d in wait] == tool_names("wait")
    for decls, top in ((replan, 2), (wait, 1)):
        testers = [d for d in decls if "tester" in d["parameters"]["properties"]]
        assert [d["name"] for d in testers] == ["robot1_place_on_tester", "robot2_pick_from_tester"]
        for d in testers:
            t = d["parameters"]["properties"]["tester"]
            assert (t["minimum"], t["maximum"]) == (1, top)
            assert ("1 or 2" in d["description"]) == (top == 2)
    # the variants are built from skill_tools.DECLARATIONS, which stays unchanged
    original = {d["name"]: d for d in DECLARATIONS}
    assert original["robot1_place_on_tester"]["parameters"]["properties"]["tester"]["maximum"] == 2
    others = [d for d in wait if "tester" not in d["parameters"]["properties"]]
    assert all(d == original[d["name"]] for d in others)


def test_check_call_refuses_tester_2_in_the_wait_run_and_wait_in_the_replan_run():
    snap, rec = FakeTools().snapshot(), Record()
    rec.holding["robot1"] = "CELL"
    wait = {d["name"]: d for d in PolicyTools(FakeTools(), "wait").declarations(tool_names("wait"))}
    replan = {d["name"]: d for d in PolicyTools(FakeTools(), "replan").declarations(tool_names("replan"))}
    assert check_call("robot1_place_on_tester", {"tester": 2}, wait, snap, rec) == \
        "schema: 2 is greater than the maximum of 1"
    assert check_call("robot1_place_on_tester", {"tester": 1}, wait, snap, rec) is None
    assert check_call("robot1_place_on_tester", {"tester": 2}, replan, snap, rec) is None
    assert check_call("wait", {"seconds": 30}, replan, snap, rec) == "unknown tool 'wait'"


def test_the_replan_run_cannot_wait():
    tools = FakeTools()
    stop, lines, _ = go([act("wait", seconds=30), act("wait", seconds=30)], tools, "replan")
    assert stop == "2 invalid outputs in a row" and tools.calls == []
    assert any("unknown tool 'wait'" in line for line in lines)


def test_the_first_cell_hook_runs_once_after_the_first_placed_cell():
    seen = []
    tools = FakeTools()
    wrapped = PolicyTools(tools, "replan", on_first_place=lambda args: seen.append((len(tools.calls), args)))
    stop = run(ScriptedModel(DRY_REPLIES), wrapped, "goal", four_slots, tool_names("replan"),
               max_steps=MAX_STEPS, out=lambda line: None)
    assert stop == "goal reached"
    assert seen == [(4, {"agv": 1, "slot": 1})]   # after pick, place, pick, place: slot 1 only


def test_a_failed_place_does_not_fire_the_first_cell_hook():
    seen = []
    tools = FakeTools(fail_once={"robot2_place_in_slot": "PRECONDITION_FAILED"})
    wrapped = PolicyTools(tools, "replan", on_first_place=seen.append)
    wrapped.call("robot2_place_in_slot", {"agv": 1, "slot": 1})
    wrapped.snapshot()
    assert seen == []


def test_main_image_only_saves_the_first_cell_image_and_the_full_tray(monkeypatch, tmp_path, capsys):
    import closed_loop
    import vlm_check
    fake_ros(monkeypatch)
    saved, lives = [], []
    monkeypatch.setattr(vlm_check, "save_image", lambda node, path: saved.append(Path(path).name) or b"png")
    monkeypatch.setattr(vlm_check, "live", lambda node, model, record, image: lives.append((model, Path(image).name)))
    monkeypatch.setenv("DEMO_OUT_DIR", str(tmp_path))
    closed_loop.main(["--policy", "replan", "--scripted", "--image-only"])
    out = capsys.readouterr().out
    assert saved == ["vlm_tray_first_cell.png"] and lives == [(None, "vlm_tray.png")]
    assert "first cell placed (agv1 slot 1): one image, to check which way the image faces" in out
    lines = out.splitlines()
    first = next(i for i, line in enumerate(lines) if "first cell placed" in line)
    assert '"slot": 1' in lines[first - 2] and lines[first + 1].startswith("obs 4:")


class FailingModel:
    """Stands in for GeminiModel: every call raises ModelError (no API call)."""

    def __init__(self, *args):
        pass

    def __call__(self, system, messages, tools):
        from gemini_model import ModelError
        raise ModelError("call 1: TimeoutError: no response in 60 wall s")


def test_main_skips_the_vlm_call_after_a_model_error(monkeypatch, tmp_path, capsys):
    import closed_loop
    import gemini_model
    import vlm_check
    fake_ros(monkeypatch)
    key = tmp_path / "key"
    key.write_text("not a key")
    monkeypatch.setenv("GEMINI_KEY_FILE", str(key))
    monkeypatch.setenv("DEMO_OUT_DIR", str(tmp_path))
    monkeypatch.setenv("DEMO_RAW_DIR", str(tmp_path / "raw"))
    monkeypatch.setattr(gemini_model, "GeminiModel", FailingModel)
    lives = []
    monkeypatch.setattr(vlm_check, "live", lambda node, model, record, image: lives.append(model))
    closed_loop.main(["--policy", "replan", "--vlm-after"])
    out = capsys.readouterr().out
    assert "stop: model error: call 1: TimeoutError" in out
    assert "the live VLM check is skipped: the agent loop stopped on a model error" in out
    assert lives == [None]   # the image is still saved; no VLM call
