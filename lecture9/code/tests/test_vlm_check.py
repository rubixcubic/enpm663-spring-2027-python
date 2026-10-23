"""vlm_check.py: the scripted run is unchanged; the image conversion; the cross-check."""
import io
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

from PIL import Image

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from vlm_check import cross_check, to_png  # noqa: E402


def test_scripted_run_output_is_unchanged():
    out = subprocess.run([sys.executable, "vlm_check.py"], cwd=HERE, capture_output=True, text=True).stdout
    assert out == (HERE / ".." / "outputs" / "vlm_check.txt").read_text()


def test_to_png_keeps_pixels_and_drops_row_padding():
    data = bytes([10, 20, 30, 40, 50, 60, 0, 0, 70, 80, 90, 100, 110, 120, 0, 0])   # 2 x 2, step 8
    png = to_png(SimpleNamespace(encoding="rgb8", width=2, height=2, step=8, data=data))
    img = Image.open(io.BytesIO(png))
    assert img.size == (2, 2) and img.getpixel((1, 1)) == (100, 110, 120)


def test_cross_check_flags_occupancy_and_missing_records():
    reply = {"slots": [{"slot": k, "occupied": True, "cell_type": "LI_ION", "damage": "NONE",
                        "confidence": 0.9} for k in (1, 2, 3, 4)]}
    status = {f"slot_{k}_occupied": k != 4 for k in (1, 2, 3, 4)}
    record = {1: 3.61, 2: 3.55, 3: None, 4: None}
    assert cross_check(reply, status, record) == [4]


# Added beyond the brief: bgr8 and other encodings, ask() with a vlm callable, the slot
# numbers check, the live model wrapper (a recording stand-in, no API call), and the
# cross-check rows for slots with no voltage record.
import json  # noqa: E402

import pytest  # noqa: E402
from vlm_check import SCHEMA, STRUCTURED, ask, check, model_vlm, VLMStop  # noqa: E402


def slots(*occupied):
    return {"slots": [{"slot": k, "occupied": o, "cell_type": "LI_ION" if o else "UNKNOWN",
                       "damage": "NONE" if o else "UNKNOWN", "confidence": 0.9}
                      for k, o in enumerate(occupied, start=1)]}


def test_to_png_swaps_bgr8_and_refuses_other_encodings():
    data = bytes([10, 20, 30])
    png = to_png(SimpleNamespace(encoding="bgr8", width=1, height=1, step=3, data=data))
    assert Image.open(io.BytesIO(png)).getpixel((0, 0)) == (30, 20, 10)
    with pytest.raises(ValueError, match="mono8"):
        to_png(SimpleNamespace(encoding="mono8", width=1, height=1, step=1, data=b"\x00"))


def test_ask_reprompts_once_with_the_error_then_stops(capsys):
    sent = []

    def vlm(prompt):
        sent.append(prompt)
        return "not json"
    assert ask(vlm, STRUCTURED) is None
    assert sent[0] == STRUCTURED and sent[1].startswith(STRUCTURED + "\nYour last reply failed: not JSON")
    assert len(sent) == 2
    assert "attempt 2: rejected" in capsys.readouterr().out


def test_ask_returns_the_first_valid_reply():
    replies = ["{}", json.dumps(slots(True, True, True, True))]
    assert ask(lambda prompt: replies.pop(0), STRUCTURED) == slots(True, True, True, True)


def test_check_refuses_a_slot_number_given_twice():
    reply = slots(True, True, True, True)
    reply["slots"][3]["slot"] = 3
    _, errors = check(json.dumps(reply))
    assert errors == ["slots: each slot number 1 to 4 must appear once, not [1, 2, 3, 3]"]


class Recorder:
    """Stands in for gemini_model.GeminiModel.ask: records each call, returns a set Reply."""

    def __init__(self, *replies):
        self.replies, self.calls = list(replies), []

    def ask(self, system, text, image_png=None, tools=None):
        self.calls.append((system, text, image_png, tools))
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


def test_model_vlm_sends_the_image_and_the_schema_with_each_prompt():
    from gemini_model import Reply
    model = Recorder(Reply(text="{}", finish_reason="STOP", usage={"input": 1100, "output": 40},
                           latency_s=1.2))
    assert model_vlm(model, b"png")("PROMPT") == "{}"
    system, text, image, tools = model.calls[0]
    assert system == "" and image == b"png" and not tools
    assert text.startswith("PROMPT\n") and json.dumps(SCHEMA) in text


def test_model_vlm_ends_on_a_cut_off_reply_or_a_model_error():
    from gemini_model import ModelError, Reply
    vlm = model_vlm(Recorder(Reply(text=None, finish_reason="MAX_TOKENS")), b"png")
    with pytest.raises(VLMStop, match="finish reason MAX_TOKENS"):
        vlm("PROMPT")
    vlm = model_vlm(Recorder(ModelError("call 9: TimeoutError: no response in 60 wall s")), b"png")
    with pytest.raises(VLMStop, match="model error: call 9: TimeoutError"):
        vlm("PROMPT")


def test_model_vlm_turns_a_reply_with_no_text_into_an_empty_string():
    from gemini_model import Reply
    assert model_vlm(Recorder(Reply(text=None, finish_reason="STOP")), b"png")("PROMPT") == ""
    _, errors = check("")
    assert errors and errors[0].startswith("not JSON")


def test_cross_check_shows_none_for_a_slot_with_no_record(capsys):
    status = {f"slot_{k}_occupied": k < 3 for k in (1, 2, 3, 4)}
    assert cross_check(slots(True, True, False, False), status, {1: 3.61, 2: None, 3: None, 4: None}) == []
    rows = capsys.readouterr().out.splitlines()
    assert rows[1] == "1     LI_ION (0.9)      occupied     LI_ION 3.61 V agree"
    assert rows[2] == "2     LI_ION (0.9)      occupied     none          agree"
    assert rows[3] == "3     empty (0.9)       empty        none          agree"


def fake_ros_msgs(monkeypatch, image, tray):
    """live() without ROS: stand-in message modules, and _latest returns the given messages."""
    import types

    import vlm_check
    for name in ("ariac_interfaces", "ariac_interfaces.msg", "sensor_msgs", "sensor_msgs.msg"):
        monkeypatch.setitem(sys.modules, name, types.SimpleNamespace(AgvTrayStatus="tray", Image="image"))
    got = {"image": image, "tray": tray}
    monkeypatch.setattr(vlm_check, "_latest", lambda node, msg_type, topic, limit=10.0: got[msg_type])


def test_live_saves_the_image_and_cross_checks_the_reply(monkeypatch, tmp_path, capsys):
    from gemini_model import Reply
    import vlm_check
    image = SimpleNamespace(encoding="rgb8", width=2, height=2, step=8,
                            data=bytes([10, 20, 30, 40, 50, 60, 0, 0, 70, 80, 90, 100, 110, 120, 0, 0]))
    tray = SimpleNamespace(**{f"slot_{k}_occupied": k != 4 for k in (1, 2, 3, 4)})
    fake_ros_msgs(monkeypatch, image, tray)
    (tmp_path / "record.json").write_text(json.dumps({"slots": {"1": 3.61, "2": 3.55, "3": 3.66, "4": None}}))
    model = Recorder(Reply(text=json.dumps(slots(True, True, True, True)), finish_reason="STOP"))
    vlm_check.live(object(), model, tmp_path / "record.json", tmp_path / "vlm_tray.png")
    out = capsys.readouterr().out
    assert Image.open(tmp_path / "vlm_tray.png").size == (2, 2)
    assert model.calls[0][2] == (tmp_path / "vlm_tray.png").read_bytes()
    assert "image: 2 x 2 rgb8 from /agv1_camera/image, saved as vlm_tray.png" in out
    assert "4     LI_ION (0.9)      empty        none          DISAGREE: occupancy" in out
    assert out.endswith("decision: do not submit; slots 4 disagree\n")


def test_live_with_no_model_only_saves_the_image(monkeypatch, tmp_path, capsys):
    import vlm_check
    image = SimpleNamespace(encoding="rgb8", width=1, height=1, step=3, data=bytes([1, 2, 3]))
    fake_ros_msgs(monkeypatch, image, None)
    vlm_check.live(object(), None, tmp_path / "record.json", tmp_path / "vlm_tray.png")
    assert (tmp_path / "vlm_tray.png").exists() and "Live VLM" not in capsys.readouterr().out


def test_live_stops_with_a_named_reason(monkeypatch, tmp_path, capsys):
    from gemini_model import Reply
    import vlm_check
    image = SimpleNamespace(encoding="rgb8", width=1, height=1, step=3, data=bytes([1, 2, 3]))
    fake_ros_msgs(monkeypatch, image, SimpleNamespace(**{f"slot_{k}_occupied": True for k in (1, 2, 3, 4)}))
    (tmp_path / "record.json").write_text(json.dumps({"slots": {str(k): 3.6 for k in (1, 2, 3, 4)}}))
    vlm_check.live(object(), Recorder(Reply(finish_reason="MAX_TOKENS")), tmp_path / "record.json",
                   tmp_path / "vlm_tray.png")
    assert capsys.readouterr().out.endswith(
        "stop: model error: reply cut off at the output cap of 1000 tokens (finish reason MAX_TOKENS); "
        "do not submit\n")
    fake_ros_msgs(monkeypatch, image, None)
    vlm_check.live(object(), Recorder(), tmp_path / "record.json", tmp_path / "vlm_tray.png")
    assert capsys.readouterr().out.endswith("no message on /agv1/tray_status: no cross-check, do not submit\n")
    fake_ros_msgs(monkeypatch, None, None)
    vlm_check.live(object(), Recorder(), tmp_path / "record.json", tmp_path / "vlm_tray.png")
    assert capsys.readouterr().out == "no image on /agv1_camera/image\n"


# Fix round 1 (I1, I3): the prompt's slot layout; submit only for a full tray with records.
from vlm_check import decision  # noqa: E402


def test_the_prompt_gives_the_tray_as_two_rows_of_two():
    assert ("The tray has four slots in two rows of two: slots 1 and 2 are the top row, left to "
            "right; slots 3 and 4 are the bottom row, left to right.") in STRUCTURED
    assert "from the left of the image" not in STRUCTURED


def test_no_submit_when_a_slot_is_empty_even_if_both_sources_agree(capsys):
    reply = slots(True, True, True, False)
    status = {f"slot_{k}_occupied": k != 4 for k in (1, 2, 3, 4)}
    record = {1: 3.61, 2: 3.55, 3: 3.66, 4: None}
    flags = cross_check(reply, status, record)
    assert flags == []
    assert decision(flags, status, record) == "decision: do not submit; slots 4 are empty or have no record"


def test_no_submit_when_an_occupied_slot_has_no_record():
    status = {f"slot_{k}_occupied": True for k in (1, 2, 3, 4)}
    assert decision([], status, {1: 3.61, 2: None, 3: 3.66, 4: 3.58}) == \
        "decision: do not submit; slots 2 are empty or have no record"


def test_submit_only_for_four_occupied_slots_with_records():
    status = {f"slot_{k}_occupied": True for k in (1, 2, 3, 4)}
    record = {1: 3.61, 2: 3.55, 3: 3.66, 4: 3.58}
    assert decision([], status, record) == "decision: all four slots agree; submit"
    assert decision([3, 4], status, record) == "decision: do not submit; slots 3 and 4 disagree"


def test_live_does_not_submit_a_tray_with_an_empty_slot(monkeypatch, tmp_path, capsys):
    from gemini_model import Reply
    import vlm_check
    image = SimpleNamespace(encoding="rgb8", width=1, height=1, step=3, data=bytes([1, 2, 3]))
    fake_ros_msgs(monkeypatch, image, SimpleNamespace(**{f"slot_{k}_occupied": k != 4 for k in (1, 2, 3, 4)}))
    (tmp_path / "record.json").write_text(json.dumps({"slots": {"1": 3.61, "2": 3.55, "3": 3.66, "4": None}}))
    model = Recorder(Reply(text=json.dumps(slots(True, True, True, False)), finish_reason="STOP"))
    vlm_check.live(object(), model, tmp_path / "record.json", tmp_path / "vlm_tray.png")
    assert capsys.readouterr().out.endswith("decision: do not submit; slots 4 are empty or have no record\n")
