"""L9 demo: check a VLM's tray record before a submit (a NiMH high-priority kit in the
scripted run, an ordinary Li-Ion kit in the live run).

Two runs share the prompt, the schema, the check and the cross-check.

The scripted run (python3 vlm_check.py): plain Python, no simulator
and no model.
- stand_in_vlm() is a scripted stand-in for a VLM. It returns canned
  replies in order, written to contain mistakes for the checker to
  find; a real model's answers vary.
- TRAY_STATUS stands in for one /agv1/tray_status message
  (AgvTrayStatus.msg: four booleans, no cell type).
- RECORD stands in for the orchestrator's own record: the voltage
  each cell read on a tester before it was placed. Values are
  chosen for this example.

The live run (live(), called by closed_loop.py --vlm-after at the
end of the replan run, in the same ARIAC launch): one
image from the camera above agv1's tray (CAMERA_TOPIC, sensor
agv1_camera in config/l9_user_config.yaml) goes to Gemini with the
structured prompt and the schema. Its reply is checked, then
cross-checked against one real /agv1/tray_status message and the
agent's own record (record.json, written by closed_loop.py).
"""
import io
import json
import sys
import textwrap
from pathlib import Path

from jsonschema import Draft7Validator

# gemini_model, orchestrator and skill_tools, imported by the live run only
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lecture8" / "code"))

NIMH_MIN, NIMH_MAX = 1.0, 1.4       # 1.2 V +/- 0.2 V, CellTypes.msg
LI_MIN, LI_MAX = 3.4, 3.8           # 3.6 V +/- 0.2 V, CellTypes.msg
CAMERA_TOPIC = "/agv1_camera/image"   # ARIAC image_plugin.cpp:47, NAME agv1_camera (config/l9_user_config.yaml)

WEAK = "Describe this image."
STRUCTURED = (
    "This image is from a camera above the tray of agv1. The tray "
    "has four slots in two rows of two: slots 1 and 2 are the top "
    "row, left to right; slots 3 and 4 are the bottom row, left to "
    "right. "
    "Return only JSON that matches the schema: one record per slot. "
    "Use UNKNOWN when you cannot see a value.")

SLOT = {
    "type": "object",
    "required": ["slot", "occupied", "cell_type", "damage",
                 "confidence"],
    "additionalProperties": False,
    "properties": {
        "slot": {"type": "integer", "minimum": 1, "maximum": 4},
        "occupied": {"type": "boolean"},
        "cell_type": {"enum": ["LI_ION", "NIMH", "UNKNOWN"]},
        "damage": {"enum": ["NONE", "DENT", "SCRATCH", "BULGE",
                            "UNKNOWN"]},
        "confidence": {"type": "number", "minimum": 0,
                       "maximum": 1},
    },
}
SCHEMA = {"type": "object", "required": ["slots"],
          "additionalProperties": False,
          "properties": {"slots": {"type": "array", "items": SLOT,
                                   "minItems": 4, "maxItems": 4}}}


def rec(slot, occupied, cell_type, damage, confidence):
    return {"slot": slot, "occupied": occupied,
            "cell_type": cell_type, "damage": damage,
            "confidence": confidence}


REPLIES = [  # what the stand-in VLM returns, call by call
    "The image shows a gray tray with four cylindrical battery "
    "cells. Most look the same. One near the right may be a "
    "different type.",
    json.dumps({"slots": [rec(k, True, "NIMH", "NONE", 0.9)
                          for k in range(0, 4)]}),
    json.dumps({"slots": [rec(1, True, "NIMH", "NONE", 0.9),
                          rec(2, True, "NIMH", "NONE", 0.85),
                          rec(3, True, "LI_ION", "NONE", 0.6),
                          rec(4, False, "UNKNOWN", "UNKNOWN", 0.7)]}),
]
TRAY_STATUS = {"slot_1_occupied": True, "slot_2_occupied": True,
               "slot_3_occupied": True, "slot_4_occupied": True}
RECORD = {1: 1.21, 2: 1.18, 3: 1.24, 4: 1.22}   # volts per slot


def stand_in_vlm(prompt, image="agv1_tray.png"):
    """Scripted stand-in for a VLM: ignores the prompt and image."""
    return REPLIES.pop(0)


def check(text):
    """Parse, then validate. Returns (record, list of errors)."""
    try:
        reply = json.loads(text)
    except json.JSONDecodeError as err:
        return None, [f"not JSON: {err.msg}"]
    errors = [f"{'.'.join(map(str, e.absolute_path))}: {e.message}"
              for e in Draft7Validator(SCHEMA).iter_errors(reply)]
    if not errors:   # the schema cannot say "each slot once"
        numbers = [r["slot"] for r in reply["slots"]]
        if sorted(numbers) != [1, 2, 3, 4]:
            errors = [f"slots: each slot number 1 to 4 must appear once, not {numbers}"]
    return reply, sorted(errors)


def ask(vlm, prompt):
    """One call, one re-prompt with the error, then stop. vlm(prompt) returns the reply text."""
    for attempt in (1, 2):
        reply, errors = check(vlm(prompt))
        print(f"  attempt {attempt}: "
              f"{'valid' if not errors else 'rejected'}")
        for error in errors[:2]:
            print(f"    {error}")
        if not errors:
            return reply
        prompt = f"{STRUCTURED}\nYour last reply failed: {errors[0]}"
        print("  re-prompt with: 'Your last reply failed: ...'")
    return None


def type_from_volts(volts):
    if NIMH_MIN <= volts <= NIMH_MAX:
        return "NIMH"
    return "LI_ION" if LI_MIN <= volts <= LI_MAX else "UNKNOWN"


def cross_check(reply, tray_status=TRAY_STATUS, record=RECORD):
    print("slot  vlm (conf.)       tray_status  record        verdict")
    flags = []
    for r in reply["slots"]:
        k = r["slot"]
        seen = "empty" if not r["occupied"] else r["cell_type"]
        topic = tray_status[f"slot_{k}_occupied"]
        volts = record.get(k)
        kind = type_from_volts(volts) if volts is not None else None
        verdict = "agree"
        if r["occupied"] != topic:
            verdict = "DISAGREE: occupancy"
        elif (kind is not None
              and r["cell_type"] not in ("UNKNOWN", kind)):
            verdict = "DISAGREE: type"
        if verdict != "agree":
            flags.append(k)
        seen = f"{seen} ({r['confidence']})"
        shown = f"{kind} {volts:.2f} V" if kind else "none"
        print(f"{k:<5} {seen:<17} {'occupied' if topic else 'empty':<12} {shown:<13} {verdict}")
    return flags


def decision(flags, tray_status=TRAY_STATUS, record=RECORD):
    """Submit only when the VLM agrees with the topic on every slot, and all four slots are
    occupied with a voltage record each: ARIAC refuses a kit with an empty slot."""
    if flags:
        return f"decision: do not submit; slots {' and '.join(map(str, flags))} disagree"
    missing = [k for k in (1, 2, 3, 4)
               if not tray_status[f"slot_{k}_occupied"] or record.get(k) is None]
    if missing:
        return f"decision: do not submit; slots {' and '.join(map(str, missing))} are empty or have no record"
    return "decision: all four slots agree; submit"


def to_png(msg):
    """A sensor_msgs/Image (rgb8 or bgr8, rows padded to msg.step) as PNG bytes."""
    import numpy as np
    from PIL import Image
    if msg.encoding not in ("rgb8", "bgr8"):
        raise ValueError(f"unexpected image encoding {msg.encoding!r}")
    rows = np.frombuffer(bytes(msg.data), dtype=np.uint8).reshape(msg.height, msg.step)
    pixels = rows[:, : msg.width * 3].reshape(msg.height, msg.width, 3)
    if msg.encoding == "bgr8":
        pixels = pixels[:, :, ::-1]
    buf = io.BytesIO()
    Image.fromarray(np.ascontiguousarray(pixels), "RGB").save(buf, "PNG")
    return buf.getvalue()


# The live prompt also carries the schema: the model sees only the prompt's text, and
# the record's keys and values (cell_type, damage, UNKNOWN) are named nowhere else.
SCHEMA_NOTE = ("Schema: " + json.dumps(SCHEMA) + "\n"
               "Reply with the JSON object only, with no code fence and no other text.")


class VLMStop(Exception):
    """The live VLM call ended without a reply to check: the reason, as the log names it."""


def model_vlm(model, png):
    """vlm(prompt) for ask(): one Gemini call with the image and the prompt plus the schema.

    Each call is a new one-message request (GeminiModel.ask), so no earlier turn is sent.
    A reply cut off before STOP, or a model error, ends the check with a named reason, as
    in the agent loop (orchestrator.cut_off)."""
    from gemini_model import ModelError
    from orchestrator import cut_off

    def vlm(prompt):
        try:
            reply = model.ask("", f"{prompt}\n{SCHEMA_NOTE}", image_png=png)
        except ModelError as err:
            raise VLMStop(f"model error: {err}") from None
        if reply.usage:
            print(f"  call: {reply.usage['input']} in, {reply.usage['output']} out tokens; "
                  f"{reply.latency_s:.2f} s")
        stop = cut_off(reply)
        if stop is not None:
            raise VLMStop(stop)
        return reply.text or ""
    return vlm


def _latest(node, msg_type, topic, limit=10.0):
    """The first message on topic within limit wall s (skill_tools.TOPIC_WAIT), or None."""
    import time

    import rclpy
    box = []
    sub = node.create_subscription(msg_type, topic, box.append, 10)
    give_up = time.monotonic() + limit
    while not box and time.monotonic() < give_up:
        rclpy.spin_once(node, timeout_sec=0.1)
    node.destroy_subscription(sub)
    return box[0] if box else None


def save_image(node, image_out):
    """One image from CAMERA_TOPIC, saved as PNG at image_out. Returns the PNG bytes, or None."""
    from sensor_msgs.msg import Image as ImageMsg
    image = _latest(node, ImageMsg, CAMERA_TOPIC)
    if image is None:
        print(f"no image on {CAMERA_TOPIC}")
        return None
    png = to_png(image)
    Path(image_out).write_bytes(png)
    print(f"image: {image.width} x {image.height} {image.encoding} from {CAMERA_TOPIC}, "
          f"saved as {Path(image_out).name}")
    return png


def live(node, model, record_path, image_out):
    """One camera image over agv1's tray to the model, checked against /agv1/tray_status and
    the agent's own record. With model None, only save the image (the dry run)."""
    from ariac_interfaces.msg import AgvTrayStatus
    from skill_tools import TRAY_TOPIC
    png = save_image(node, image_out)
    if png is None or model is None:
        return
    tray = _latest(node, AgvTrayStatus, TRAY_TOPIC.format(n=1))
    if tray is None:
        print(f"no message on {TRAY_TOPIC.format(n=1)}: no cross-check, do not submit")
        return
    status = {f"slot_{k}_occupied": bool(getattr(tray, f"slot_{k}_occupied")) for k in (1, 2, 3, 4)}
    record = {int(k): v for k, v in json.loads(Path(record_path).read_text())["slots"].items()}
    print("Live VLM, one image of agv1's tray")
    try:
        reply = ask(model_vlm(model, png), STRUCTURED)
    except VLMStop as stop:
        print(f"stop: {stop}; do not submit")
        return
    if reply is None:
        print("no valid record: stop and report")
        return
    # The live run fills an ordinary Li-Ion kit, so its submit is /submit_kitting_order,
    # not the service named below. The recorded log (outputs/closed_loop_replan_rec1.txt)
    # has this line, so it stays: changing the printed text would need a new recording.
    print("Cross-check before /submit_high_priority_order:")
    flags = cross_check(reply, status, record)
    print(decision(flags, status, record))


def main():
    print("Scripted stand-in VLM (a real model's answers vary)")
    print(f"Weak prompt: {WEAK!r}")
    text = stand_in_vlm(WEAK)
    for row in textwrap.wrap(text, 64):
        print(f"  | {row}")
    _, errors = check(text)
    print(f"  check: {errors[0]}")
    print("Structured prompt with the schema:")
    reply = ask(stand_in_vlm, STRUCTURED)
    if reply is None:
        print("no valid record: stop and report")
        return
    print("Cross-check before /submit_high_priority_order:")
    print(decision(cross_check(reply), TRAY_STATUS, RECORD))


if __name__ == "__main__":
    main()
