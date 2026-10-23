"""gemini_model.py against three recorded responses (tests/fixtures), and the key rules."""
import copy
import json
import os
import time
from pathlib import Path

import pytest

from gemini_model import (GeminiModel, ModelError, Reply, billed_output, build_request,
                          parse_raw, read_key, to_declaration, usage_from_raw, SUPPORTED_KEYS)
from skill_tools import DECLARATIONS

FIX = Path(__file__).parent / "fixtures"
KEY = "test-key-0123456789"   # a fake key, chosen for these tests


def raw(name):
    return json.loads((FIX / f"{name}.json").read_text())


def duplicate_first_call(raw):
    """Add a second call after the first, as a parallel call would come (F5, F6).

    The parts list is raw["candidates"][0]["content"]["parts"] in function_call.json.
    F6: only the first call of a turn carries the thought signature, so the copy has none,
    and it gets its own id."""
    parts = raw["candidates"][0]["content"]["parts"]
    i = next(n for n, p in enumerate(parts) if "function_call" in p)
    second = copy.deepcopy(parts[i])
    second.pop("thought_signature", None)
    second["function_call"]["id"] = "second-call"
    parts.insert(i + 1, second)


def test_parse_function_call():
    r = parse_raw(raw("function_call"))
    assert r.tool == "robot2_move_home" and r.args == {} and r.dropped_calls == 0
    assert r.usage["input"] > 0 and r.usage["output"] >= 0 and r.model_version


def test_parse_text_reply():
    r = parse_raw(raw("tool_reply"))
    assert r.tool is None and r.text


def test_parse_image_reply_names_the_color():
    r = parse_raw(raw("image_reply"))
    assert "red" in r.text.lower()


def test_parse_two_calls_keeps_the_first():
    two = copy.deepcopy(raw("function_call"))
    # Duplicate the call part at the place F5 names; written against the fixture's own shape.
    duplicate_first_call(two)
    r = parse_raw(two)
    assert r.tool == "robot2_move_home" and r.dropped_calls == 1


def test_usage_and_billing():
    u = usage_from_raw(raw("function_call"))
    assert set(u) == {"input", "output", "thoughts", "total"}
    assert billed_output(u) >= u["output"]


def test_declarations_keep_only_supported_keys():
    for d in DECLARATIONS:
        out = to_declaration(d)
        assert out["name"] == d["name"] and out["description"] == d["description"]
        stack = [out.get("parameters", {})]
        while stack:
            node = stack.pop()
            assert set(node) <= SUPPORTED_KEYS | {"properties"}, (d["name"], set(node) - SUPPORTED_KEYS)
            stack.extend(node.get("properties", {}).values())


def test_history_sends_the_model_turn_back_unchanged():
    marker = object()
    msgs = [{"role": "user", "text": "go", "image_png": None},
            {"role": "model", "reply": Reply(tool="robot2_move_home", args={}, raw_content=marker)},
            {"role": "tool", "name": "robot2_move_home", "response": {"result": {"code": "SUCCESS"}}}]
    request = build_request("m", "sys", msgs, DECLARATIONS[:1])
    assert any(c is marker for c in request["contents"])


def test_read_key_refuses_a_readable_file(tmp_path):
    f = tmp_path / "k"
    f.write_text(KEY + "\n")
    os.chmod(f, 0o644)
    with pytest.raises(ModelError, match="mode 600"):
        read_key(f)
    os.chmod(f, 0o600)
    assert read_key(f) == KEY


def test_repr_has_no_key(tmp_path):
    m = GeminiModel("m", None, tmp_path, client=object())
    m._key = KEY
    assert KEY not in repr(m)


def test_error_text_never_holds_the_key(tmp_path, monkeypatch):
    import gemini_model
    m = GeminiModel("m", None, tmp_path, client=object())
    m._key = KEY

    def boom(client, request):
        raise RuntimeError(f"401 for url ...?key={KEY}")
    monkeypatch.setattr(gemini_model, "send_request", boom)
    with pytest.raises(ModelError) as err:
        m("sys", [{"role": "user", "text": "hi", "image_png": None}], [])
    assert KEY not in str(err.value) and "<key>" in str(err.value)
    assert err.value.__cause__ is None and err.value.__suppress_context__


def test_raw_files_never_hold_the_key(tmp_path, monkeypatch):
    import gemini_model
    m = GeminiModel("m", None, tmp_path, client=object())
    m._key = KEY
    leaky = raw("tool_reply")
    leaky["echo"] = KEY
    monkeypatch.setattr(gemini_model, "send_request", lambda client, request: leaky)
    monkeypatch.setattr(gemini_model, "dump_response", lambda response: response)
    monkeypatch.setattr(gemini_model, "model_content", lambda response: None)
    m("sys", [{"role": "user", "text": "hi", "image_png": None}], [])
    for f in tmp_path.iterdir():
        assert KEY not in f.read_text(), f.name
    assert json.loads((tmp_path / "call_001.meta.json").read_text())["latency_s"] >= 0


# Added in Task 4 for the Task 1 findings: call ids (F5, F6), parallel calls (F6),
# the enum type (F4), the wall-clock limit (F2, F12) and the request config (F3, F7, F8).

def test_parse_keeps_the_call_id_and_the_dropped_calls():
    r = parse_raw(raw("function_call"))
    assert r.call_id and r.dropped == []
    two = copy.deepcopy(raw("function_call"))
    duplicate_first_call(two)
    r = parse_raw(two)
    assert r.dropped == [{"name": "robot2_move_home", "id": "second-call"}]


def test_tool_turn_answers_the_call_id():
    reply = Reply(tool="read_conveyor", args={}, call_id="abc", raw_content=object())
    base = [{"role": "user", "text": "go", "image_png": None}, {"role": "model", "reply": reply}]
    with_id = base + [{"role": "tool", "name": "read_conveyor", "id": "abc", "response": {"r": 1}}]
    without_id = base + [{"role": "tool", "name": "read_conveyor", "response": {"r": 1}}]
    for msgs in (with_id, without_id):
        turn = build_request("m", "sys", msgs, [])["contents"][-1]
        assert turn == {"role": "user", "parts": [
            {"function_response": {"name": "read_conveyor", "response": {"r": 1}, "id": "abc"}}]}


def test_dropped_calls_get_a_not_run_answer():
    reply = Reply(tool="read_conveyor", args={}, call_id="a", dropped_calls=1,
                  dropped=[{"name": "read_testers", "id": "b"}], raw_content=object())
    msgs = [{"role": "user", "text": "go", "image_png": None}, {"role": "model", "reply": reply},
            {"role": "tool", "name": "read_conveyor", "response": {"r": 1}}]
    parts = build_request("m", "sys", msgs, [])["contents"][-1]["parts"]
    assert [p["function_response"]["id"] for p in parts] == ["a", "b"]
    assert "not run" in parts[1]["function_response"]["response"]["error"]


def test_a_rebuilt_model_turn_carries_the_call():
    msgs = [{"role": "user", "text": "go", "image_png": None},
            {"role": "model", "reply": Reply(tool="wait", args={"seconds": 5}, call_id="w1")}]
    turn = build_request("m", "sys", msgs, [])["contents"][-1]
    assert turn == {"role": "model", "parts": [
        {"function_call": {"name": "wait", "args": {"seconds": 5}, "id": "w1"}}]}


def test_enum_gets_a_string_type():
    from validator import SCHEMA
    out = to_declaration({"name": "move_agv", "description": "d", "parameters": SCHEMA})
    assert out["parameters"]["properties"]["station"]["type"] == "string"
    assert "additionalProperties" not in out["parameters"]
    with pytest.raises(ValueError, match="enum"):
        to_declaration({"name": "x", "description": "d",
                        "parameters": {"type": "object", "properties": {"n": {"enum": [1, 2]}}}})


def test_request_config():
    png = b"\x89PNG fake bytes"
    msgs = [{"role": "user", "text": "what color?", "image_png": png}]
    req = build_request("m", "", msgs, DECLARATIONS[:1])
    assert req["model"] == "m" and "system_instruction" not in req["config"]
    assert req["contents"][0]["parts"] == [{"inline_data": {"mime_type": "image/png", "data": png}},
                                           {"text": "what color?"}]
    cfg = req["config"]
    assert cfg["tool_config"] == {"function_calling_config": {"mode": "AUTO"}}
    assert cfg["automatic_function_calling"] == {"disable": True}
    assert cfg["max_output_tokens"] == 1000
    assert cfg["tools"][0]["function_declarations"][0]["name"] == DECLARATIONS[0]["name"]
    no_tools = build_request("m", "sys", msgs, [])["config"]
    assert no_tools["system_instruction"] == "sys" and "tools" not in no_tools


def test_a_slow_call_ends_at_the_wall_limit(tmp_path, monkeypatch):
    import gemini_model
    m = GeminiModel("m", None, tmp_path, client=object())
    monkeypatch.setattr(gemini_model, "CALL_TIMEOUT_S", 0.2)   # chosen: a short limit for the test
    monkeypatch.setattr(gemini_model, "send_request", lambda client, request: time.sleep(5))
    t0 = time.monotonic()
    with pytest.raises(ModelError, match="no response in 0.2 wall s"):
        m("sys", [{"role": "user", "text": "hi", "image_png": None}], [])
    assert time.monotonic() - t0 < 2


# Added in Task 5: the finish reason, so the loop can tell a reply cut off at the
# output cap (MAX_TOKENS) from an empty answer.

def test_parse_keeps_the_finish_reason():
    for name in ("function_call", "tool_reply", "image_reply"):
        assert parse_raw(raw(name)).finish_reason == "STOP"
    cut = copy.deepcopy(raw("tool_reply"))
    cut["candidates"][0]["finish_reason"] = "MAX_TOKENS"   # the shape a cut-off reply takes; not recorded
    cut["candidates"][0]["content"]["parts"] = []
    r = parse_raw(cut)
    assert r.tool is None and r.text is None and r.finish_reason == "MAX_TOKENS"
    rest = {"candidates": [{"finishReason": "MAX_TOKENS", "content": {"parts": []}}]}   # REST names
    assert parse_raw(rest).finish_reason == "MAX_TOKENS"
    assert parse_raw({}).finish_reason is None
