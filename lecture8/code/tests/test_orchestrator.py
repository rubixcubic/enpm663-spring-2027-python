"""The orchestrator loop with ScriptedModel and FakeTools: stop conditions, checks, record."""
import copy
import json
from pathlib import Path

import pytest

import orchestrator
from fake_tools import FakeTools
from gemini_model import MAX_OUTPUT_TOKENS, ModelError, Reply, parse_raw
from orchestrator import (MAX_INVALID, Record, ScriptedModel, as_reply, guard, one_cell_in_slot,
                          run, summary)
from skill_tools import L8_TOOLS

FIX = Path(__file__).parent / "fixtures"


def act(name, **args):
    return {"tool": name, "args": args}


DONE = {"text": "done"}
GOOD_PATH = [act("robot1_pick_from_conveyor"), act("robot1_place_on_tester", tester=1),
             act("robot2_pick_from_tester", tester=1), act("robot2_place_in_slot", agv=1, slot=1), DONE]


def run_fake(replies, tools=None, **kw):
    lines = []
    tools = tools or FakeTools()
    stop = run(ScriptedModel(replies), tools, "goal", one_cell_in_slot, L8_TOOLS, out=lines.append, **kw)
    return stop, lines, tools


def snap(t1=(0.0, "OPERATIONAL"), t2=(0.0, "OPERATIONAL"), station="INSPECTION", slots=None,
         conveyor="OPERATIONAL"):
    agv = {"station": station, "slots": slots or {"1": False, "2": False, "3": False, "4": False}}
    return {"sim_time_s": 0.0,
            "testers": {"1": {"voltage": t1[0], "status": t1[1]}, "2": {"voltage": t2[0], "status": t2[1]}},
            "conveyor": {"status": conveyor, "speed": 0.1}, "agvs": {"1": agv, "2": agv, "3": agv}}


def test_good_path_reaches_the_goal():
    stop, _, tools = run_fake(GOOD_PATH)
    assert stop == "goal reached"
    assert [n for n, _ in tools.calls] == [r["tool"] for r in GOOD_PATH[:-1]]


def test_step_limit():
    stop, _, tools = run_fake([act("read_conveyor")] * 3, max_steps=3)
    assert stop == "step limit" and len(tools.calls) == 3


def test_done_before_the_goal_goes_back_to_the_model():
    stop, lines, _ = run_fake([DONE] + GOOD_PATH)
    assert stop == "goal reached" and any("goal not reached" in line for line in lines)


def test_two_refused_calls_in_a_row_stop_the_run():
    stop, _, tools = run_fake([act("robot2_pick_from_tester", tester=1)] * 2)
    assert stop == f"{MAX_INVALID} invalid outputs in a row" and tools.calls == []


def test_a_valid_call_resets_the_invalid_count():
    bad = act("robot2_pick_from_tester", tester=1)
    stop, _, _ = run_fake([bad, act("read_conveyor"), bad, act("read_conveyor")], max_steps=4)
    assert stop == "step limit"


def test_schema_error_is_refused():
    stop, lines, tools = run_fake([act("robot1_place_on_tester", tester=3)] * 2)
    assert tools.calls == [] and any("schema:" in line for line in lines)


def test_unknown_tool_is_refused():
    _, lines, _ = run_fake([act("move_agv", agv=1)] * 2)
    assert any("unknown tool 'move_agv'" in line for line in lines)


def test_wait_is_not_offered_in_l8():
    _, lines, _ = run_fake([act("wait", seconds=10)] * 2)
    assert any("unknown tool 'wait'" in line for line in lines)


def test_a_skill_failure_goes_back_and_is_not_an_invalid_output():
    tools = FakeTools(fail_once={"robot1_pick_from_conveyor": "PRECONDITION_FAILED"})
    stop, lines, _ = run_fake([GOOD_PATH[0]] + GOOD_PATH, tools=tools)
    assert stop == "goal reached" and any("PRECONDITION_FAILED" in line for line in lines)


def test_model_error_ends_the_run_without_a_retry():
    calls = []

    def broken(system, messages, tools):
        calls.append(1)
        raise ModelError("call 1: TimeoutError: timed out")
    stop = run(broken, FakeTools(), "goal", one_cell_in_slot, L8_TOOLS, out=lambda s: None)
    assert stop == "model error: call 1: TimeoutError: timed out" and calls == [1]


def fixture_reply(name, edit=None):
    """A Reply from a recorded response (tests/fixtures), as GeminiModel builds it.

    edit(raw) changes the response first. latency_s is set as GeminiModel._send sets it;
    0.5 s is chosen for these tests. raw_content stays None: these replies go to
    ScriptedModel only, never back to Gemini."""
    raw = json.loads((FIX / f"{name}.json").read_text())
    if edit:
        edit(raw)
    reply = parse_raw(raw)
    reply.latency_s = 0.5
    return reply


def add_a_second_call(raw):
    """A parallel call after the first one, in function_call.json's shape (as in test_gemini_model.py)."""
    parts = raw["candidates"][0]["content"]["parts"]
    second = copy.deepcopy(parts[0])
    second.pop("thought_signature", None)
    second["function_call"]["id"] = "second-call"
    parts.append(second)


def test_extra_calls_in_one_reply_are_reported():
    # Task 4: only parse_raw fills Reply.dropped, so the reply comes from a recorded
    # response with a second call added, not from Reply(dropped_calls=1).
    reply = fixture_reply("function_call", add_a_second_call)
    assert reply.dropped_calls == 1 and len(reply.dropped) == 1
    _, lines, tools = run_fake([reply], max_steps=1)
    assert any("ran the first of 2 calls" in line for line in lines)
    assert [n for n, _ in tools.calls] == ["robot2_move_home"]


def test_every_step_logs_observation_choice_and_result():
    _, lines, _ = run_fake(GOOD_PATH)
    assert lines[0].startswith("goal:") and lines[1].startswith("obs 0:")
    assert sum(line.startswith("  model:") for line in lines) == 5
    assert sum(line.startswith("  result:") for line in lines) == 4
    assert sum(line.startswith("obs ") for line in lines) == 5


def test_as_reply():
    assert as_reply({"tool": "x", "args": {"a": 1}}) == Reply(tool="x", args={"a": 1})
    assert as_reply({"text": "done"}).text == "done"


def test_guard_holding():
    rec = Record()
    assert guard("robot1_place_on_tester", {"tester": 1}, snap(), rec) == "robot 1 holds NOTHING, needs CELL"
    rec.holding["robot2"] = "CELL"
    assert guard("robot2_pick_from_tester", {"tester": 1}, snap(t1=(3.6, "OPERATIONAL")), rec) == \
        "robot 2 holds CELL, needs NOTHING"


def test_guard_testers():
    rec = Record()
    rec.holding["robot1"] = "CELL"
    s = snap(t1=(-1.0, "MALFUNCTIONING"))
    assert guard("robot1_place_on_tester", {"tester": 1}, s, rec) == "tester 1 is MALFUNCTIONING"
    assert guard("robot1_place_on_tester", {"tester": 2}, s, rec) is None
    assert guard("robot1_place_on_tester", {"tester": 1}, snap(t1=(3.61, "OPERATIONAL")), rec) == \
        "tester 1 already holds a cell (3.61 V)"
    assert guard("robot2_pick_from_tester", {"tester": 2}, s, Record()) == "tester 2 is empty (0.00 V)"
    assert guard("robot2_pick_from_tester", {"tester": 1}, s, Record()) is None
    assert guard("robot1_place_on_tester", {"tester": 1}, snap(t1=(None, "NO_READING")), rec) == \
        "no reading from tester 1"


def test_guard_conveyor():
    assert guard("robot1_pick_from_conveyor", {}, snap(conveyor="MALFUNCTIONING"), Record()) == \
        "the conveyor is MALFUNCTIONING"


def test_guard_slots():
    rec = Record()
    rec.holding["robot2"] = "CELL"
    args = {"agv": 1, "slot": 1}
    assert guard("robot2_place_in_slot", args, snap(), rec) == "the held cell has no voltage record"
    rec.held_volts = 3.2
    assert guard("robot2_place_in_slot", args, snap(), rec) == "the held cell read 3.20 V, outside 3.4 to 3.8 V"
    rec.held_volts = 3.6
    assert guard("robot2_place_in_slot", args, snap(), rec) is None
    assert guard("robot2_place_in_slot", args, snap(station="SHIPPING"), rec) == \
        "agv1 is at SHIPPING, not INSPECTION"
    full = {"1": True, "2": False, "3": False, "4": False}
    assert guard("robot2_place_in_slot", args, snap(slots=full), rec) == "agv1 slot 1 is occupied"


def test_record_follows_a_cell_from_tester_to_slot():
    rec = Record()
    rec.observe(snap(t1=(3.61, "OPERATIONAL")))
    rec.after("robot2_pick_from_tester", {"tester": 1}, {"code": "SUCCESS", "holding": "CELL"})
    assert rec.held_volts == 3.61 and rec.on_tester[1] is None and rec.holding["robot2"] == "CELL"
    rec.after("robot2_place_in_slot", {"agv": 1, "slot": 1}, {"code": "SUCCESS", "holding": "NOTHING"})
    assert rec.slots == {(1, 1): 3.61} and rec.held_volts is None


def test_record_keeps_a_reading_through_a_malfunction():
    rec = Record()
    rec.observe(snap(t1=(3.61, "OPERATIONAL")))
    rec.observe(snap(t1=(-1.0, "MALFUNCTIONING")))
    assert rec.on_tester[1] == 3.61
    rec.observe(snap(t1=(0.01, "OPERATIONAL")))
    assert rec.on_tester[1] is None


def test_record_takes_holding_from_a_failed_result():
    rec = Record()
    rec.holding["robot2"] = "CELL"
    rec.after("robot2_place_in_slot", {"agv": 1, "slot": 1}, {"code": "GRASP_FAILED", "holding": "NOTHING"})
    assert rec.holding["robot2"] == "NOTHING" and rec.slots == {}


def test_extra_guard_is_applied():
    refuse = lambda name, args, s, rec: "policy: no" if name == "read_conveyor" else None  # noqa: E731
    stop, lines, _ = run_fake([act("read_conveyor")] * 2, extra_guard=refuse)
    assert stop == f"{MAX_INVALID} invalid outputs in a row" and any("policy: no" in line for line in lines)


# Added in Task 5 for what Tasks 3 and 4 pass on: results with holding None, the
# NO_READING snapshot, tool message ids, the model's own turns, and a cut-off reply.

class Recorder:
    """A model that returns fixed replies and keeps a copy of the messages of each call."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.returned = []
        self.seen = []

    def __call__(self, system, messages, tools):
        self.seen.append(list(messages))
        reply = self.replies.pop(0)
        self.returned.append(reply)
        return reply


def no_goal_result(code):
    """An act result for a goal that was never sent or never answered (Task 3: SkillTools._failed)."""
    return {"code": code, "holding": None, "message": "chosen for this test", "attempts": None,
            "wall_s": None}


@pytest.mark.parametrize("name, code", [("robot1_place_on_tester", "NO_SERVER"),
                                        ("robot1_place_on_tester", "REJECTED"),
                                        ("robot1_place_on_tester", "TIMEOUT"),
                                        ("robot1_pick_from_conveyor", "NO_CELL")])
def test_record_keeps_a_known_holding_when_the_result_has_none(name, code):
    rec = Record()
    rec.holding["robot1"] = "CELL"
    rec.after(name, {"tester": 1}, no_goal_result(code))
    assert rec.holding["robot1"] == "CELL"


def test_a_result_with_no_holding_does_not_clear_the_record_in_a_run():
    class LostServer(FakeTools):
        """robot 1's place goal is never sent once; the fake still holds the cell."""

        def call(self, name, args):
            if name == "robot1_place_on_tester" and not getattr(self, "lost", False):
                self.lost = True
                self.calls.append((name, dict(args)))
                return no_goal_result("NO_SERVER")
            return super().call(name, args)
    stop, lines, _ = run_fake([GOOD_PATH[0], GOOD_PATH[1]] + GOOD_PATH[1:], tools=LostServer())
    assert stop == "goal reached" and any("NO_SERVER" in line for line in lines)
    after_lost = next(line for line in lines if line.startswith("obs 2:"))
    assert "robot 1 CELL" in after_lost


NO_READING_SNAP = {"sim_time_s": 0.0,
                   "testers": {"1": {"voltage": None, "status": "NO_READING"},
                               "2": {"voltage": None, "status": "NO_READING"}},
                   "conveyor": {"status": "NO_READING", "speed": None},
                   "agvs": {a: {"station": "NO_READING", "slots": "NO_READING"} for a in ("1", "2", "3")}}


def test_the_no_reading_snapshot_is_handled():
    s = copy.deepcopy(NO_READING_SNAP)
    rec = Record()
    rec.on_tester[1] = 3.61
    rec.observe(s)
    assert rec.on_tester == {1: 3.61, 2: None}
    assert not one_cell_in_slot(s, rec)
    line = summary(s, rec)
    assert "tester 1 ? V NO_READING" in line and "conveyor NO_READING" in line and "slots ?" in line
    rec.holding["robot1"] = "CELL"
    assert guard("robot1_place_on_tester", {"tester": 1}, s, rec) == "no reading from tester 1"
    assert guard("robot2_pick_from_tester", {"tester": 2}, s, Record()) == "no reading from tester 2"
    rec.holding["robot2"], rec.held_volts = "CELL", 3.6
    assert guard("robot2_place_in_slot", {"agv": 1, "slot": 1}, s, rec) == \
        "agv1 is at NO_READING, not INSPECTION"
    s["agvs"]["1"]["station"] = "INSPECTION"
    assert guard("robot2_place_in_slot", {"agv": 1, "slot": 1}, s, rec) == "no tray reading for agv1"


def test_a_run_on_the_no_reading_snapshot_does_not_crash():
    class Blind(FakeTools):
        def snapshot(self):
            return copy.deepcopy(NO_READING_SNAP)
    stop, lines, tools = run_fake([DONE, act("robot1_pick_from_conveyor"),
                                   act("robot1_place_on_tester", tester=1)], tools=Blind(), max_steps=3)
    assert stop == "step limit" and any("goal not reached" in line for line in lines)
    assert any("no reading from tester 1" in line for line in lines)
    assert [n for n, _ in tools.calls] == ["robot1_pick_from_conveyor"]


def test_every_tool_message_carries_the_call_id():
    model = Recorder([Reply(tool="robot1_pick_from_conveyor", args={}, call_id="c1"),
                      Reply(tool="robot2_pick_from_tester", args={"tester": 1}, call_id="c2"),
                      Reply(text="done")])
    run(model, FakeTools(), "goal", one_cell_in_slot, L8_TOOLS, max_steps=3, out=lambda s: None)
    tool_messages = [m for m in model.seen[-1] if m["role"] == "tool"]
    assert [(m["name"], m["id"]) for m in tool_messages] == [("robot1_pick_from_conveyor", "c1"),
                                                             ("robot2_pick_from_tester", "c2")]
    assert "refused" in tool_messages[1]["response"]["result"]["error"]


def test_the_history_holds_only_the_models_own_turns():
    model = Recorder([as_reply(r) for r in GOOD_PATH])
    run(model, FakeTools(), "goal", one_cell_in_slot, L8_TOOLS, out=lambda s: None)
    turns = [m["reply"] for m in model.seen[-1] if m["role"] == "model"]
    assert len(turns) == 4 and all(t is r for t, r in zip(turns, model.returned))


def test_fake_run_1_without_a_key_runs_the_scripted_model(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("GEMINI_KEY_FILE", str(tmp_path / "no_key"))
    monkeypatch.delenv("DEMO_RAW_DIR", raising=False)
    orchestrator.main(["--fake", "--runs", "1"])
    out = capsys.readouterr().out
    assert f"no key file at {tmp_path / 'no_key'}: Run 1 uses the scripted model" in out
    assert "(scripted model: fixed replies) ===" in out and "Gemini" not in out
    assert out.rstrip().endswith("stop: goal reached")


def cut_off(text=None):
    """tool_reply.json, as a reply stopped at the output cap would come: finish_reason
    MAX_TOKENS, and no part, or one part of partial text. Built from the recorded shape;
    no MAX_TOKENS response was recorded."""
    def edit(raw):
        cand = raw["candidates"][0]
        cand["finish_reason"] = "MAX_TOKENS"
        cand["content"]["parts"] = [{"text": text}] if text else []
    return edit


@pytest.mark.parametrize("text", [None, "I will pick the next ce"])
def test_a_reply_cut_off_at_the_output_cap_ends_the_run(text):
    reply = fixture_reply("tool_reply", cut_off(text))
    assert reply.tool is None and reply.finish_reason == "MAX_TOKENS"
    stop, lines, tools = run_fake([reply] + GOOD_PATH)
    assert stop == (f"model error: reply cut off at the output cap of {MAX_OUTPUT_TOKENS} tokens "
                    "(finish reason MAX_TOKENS)")
    assert tools.calls == [] and not any("goal not reached" in line for line in lines)
    assert any(line.startswith("  model:  no tool call, finish reason MAX_TOKENS") for line in lines)


def test_a_finished_text_reply_is_still_an_answer():
    reply = fixture_reply("tool_reply")
    assert reply.finish_reason == "STOP"
    stop, lines, _ = run_fake([reply] + GOOD_PATH)
    assert stop == "goal reached" and any("goal not reached" in line for line in lines)


def test_another_finish_reason_with_no_call_ends_the_run_too():
    def blocked(raw):
        # chosen for this test: any reason other than STOP. The facts file quotes only
        # STOP (the fixtures) and MAX_TOKENS (F9); this name is not checked against the docs.
        raw["candidates"][0]["finish_reason"] = "SAFETY"
        raw["candidates"][0]["content"]["parts"] = []
    stop, _, tools = run_fake([fixture_reply("tool_reply", blocked)] + GOOD_PATH)
    assert stop == "model error: reply ended with finish reason SAFETY" and tools.calls == []
