"""er_demo.py: the offline stand-in, and the live client against a mock server.

No key and no network: every live test gives make_live_client an httpx mock transport."""
import base64
import json
import time

import httpx
import pytest

import er_demo

FAKE_KEY = "FAKE-KEY-0123456789-not-a-real-key"
PNG = er_demo.placeholder_png()


def interaction(text, model="gemini-robotics-er-2-preview"):
    """A response body in the shape the stand-in uses, with a usage block
    (field names from https://ai.google.dev/api/interactions-api, read 2026-10-18)."""
    return {"id": "test-1", "model": model, "status": "completed",
            "steps": [{"type": "model_output", "content": [{"type": "text", "text": text}]}],
            "usage": {"total_input_tokens": 1200, "total_output_tokens": 30,
                      "total_thought_tokens": 400, "total_tokens": 1630}}


def live(tmp_path, handler, images=None):
    rec = er_demo.Recorder(tmp_path, FAKE_KEY)
    client = er_demo.make_live_client(FAKE_KEY, rec, transport=httpx.MockTransport(handler))
    images = images or {"c01": PNG}
    return er_demo.ask_live(client, rec, images, log=lambda s: None), rec


def every_file(tmp_path):
    return {p.name: p.read_text() for p in tmp_path.iterdir()}


def test_offline_mode_is_the_scripted_stand_in():
    stand_in, results = er_demo.ask_all()
    assert len(stand_in.requests) == 12
    rejected = [c for c, (_, _, errors) in results.items() if errors]
    assert rejected == ["c10"]


def test_live_call_sends_the_deck_request_and_records_it(tmp_path):
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json=interaction('{"defective": false, "defects": []}'))
    results, _ = live(tmp_path, handler)
    assert len(seen) == 1
    req = seen[0]
    assert req.url.path == "/v1beta/interactions"
    assert req.headers["x-goog-api-key"] == FAKE_KEY       # the SDK sends the key in this header
    body = json.loads(req.content)
    assert body["model"] == er_demo.MODEL
    assert body["generation_config"] == {"thinking_level": "medium"}
    parts = body["input"][0]["content"]
    assert base64.b64decode(parts[0]["data"]) == PNG
    assert parts[1]["text"] == er_demo.PROMPT
    rec = results["c01"]
    assert rec["error"] is None and rec["errors"] == [] and rec["http_status"] == 200
    assert rec["answer"] == {"defective": False, "defects": []}
    saved = json.loads((tmp_path / "c01.request.json").read_text())
    assert saved["headers"]["x-goog-api-key"] == "<key>"
    assert "sha256" in saved["body"]["input"][0]["content"][0]["data"]
    assert json.loads((tmp_path / "c01.response.json").read_text())["usage"]["total_input_tokens"] == 1200


def test_no_file_holds_the_key(tmp_path):
    def handler(request):   # an error body that echoes the key
        return httpx.Response(400, json={"error": {"code": 400, "message": f"bad key {FAKE_KEY}",
                                                   "status": "INVALID_ARGUMENT"}})
    results, _ = live(tmp_path, handler, {"c01": PNG, "c02": PNG})
    files = every_file(tmp_path)
    assert files and not any(FAKE_KEY in text for text in files.values())
    assert results["c01"]["error"] and FAKE_KEY not in results["c01"]["error"]


def test_a_failed_call_is_never_sent_again(tmp_path):
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(503, json={"error": {"code": 503, "message": "busy", "status": "UNAVAILABLE"}})
    results, _ = live(tmp_path, handler, {"c01": PNG, "c02": PNG})
    assert len(calls) == 2                       # one request per cell, no retry
    assert all(r["requests_sent"] == 2 for r in results.values())   # the second was blocked
    assert all("SecondRequest" in r["error"] for r in results.values())
    assert json.loads((tmp_path / "c01.status.json").read_text())["status"] == 503


def test_a_key_or_quota_error_stops_the_other_calls(tmp_path):
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(403, json={"error": {"code": 403, "message": "no", "status": "PERMISSION_DENIED"}})
    results, _ = live(tmp_path, handler, {"c01": PNG, "c02": PNG, "c03": PNG})
    assert len(calls) == 1 and list(results) == ["c01"]


def test_a_call_with_no_answer_in_time_stops_the_run(tmp_path, monkeypatch):
    monkeypatch.setattr(er_demo, "CALL_TIMEOUT_S", 0.5)

    def handler(request):
        time.sleep(1.5)
        return httpx.Response(200, json=interaction("{}"))
    results, _ = live(tmp_path, handler, {"c01": PNG, "c02": PNG})
    assert list(results) == ["c01"] and results["c01"]["error"].startswith("TimeoutError")


def test_an_answer_with_a_code_fence_is_rejected_not_repaired(tmp_path):
    def handler(request):
        return httpx.Response(200, json=interaction('```json\n{"defective": false, "defects": []}\n```'))
    results, _ = live(tmp_path, handler)
    assert results["c01"]["errors"] and results["c01"]["errors"][0].startswith("not JSON")


def test_run2_asks_for_structured_output_and_no_storage(tmp_path):
    seen = []

    def handler(request):
        seen.append((time.monotonic(), json.loads(request.content)))
        return httpx.Response(200, json=interaction('{"defective": false, "defects": []}'))
    rec = er_demo.Recorder(tmp_path, FAKE_KEY)
    client = er_demo.make_live_client(FAKE_KEY, rec, transport=httpx.MockTransport(handler))
    er_demo.ask_live(client, rec, {"c01": PNG, "c02": PNG}, log=lambda s: None,
                     extra=er_demo.STRUCTURED, gap_s=1.0)
    (t1, body), (t2, _) = seen
    assert body["response_format"] == {"type": "text", "mime_type": "application/json",
                                       "schema": er_demo.ANSWER_SCHEMA}
    assert body["store"] is False
    assert body["generation_config"] == {"thinking_level": "medium"}
    # the gap runs from one call's start in ask_live to the next; the first call's
    # SDK setup (about 0.25 s here) falls inside it, so the requests arrive a bit closer
    assert t2 - t1 >= 0.7


def test_run1_request_has_no_structured_output(tmp_path):
    seen = []

    def handler(request):
        seen.append(json.loads(request.content))
        return httpx.Response(200, json=interaction("{}"))
    live(tmp_path, handler)
    assert set(seen[0]) == {"model", "generation_config", "input"}
