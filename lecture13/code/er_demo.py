"""L13 demonstration: ask an embodied-reasoning model about a cell.

The client side is the real google-genai SDK, called the way the
Gemini API robotics overview page shows (client.interactions.create).
The same prompt, call (ask) and schema check (check) run in two modes.

Offline mode (python3 er_demo.py): the server side is a SCRIPTED
STAND-IN. No API key is used: an httpx mock transport catches each
request and returns answers written in advance. A real model's answers
vary. The images are synthetic 8 x 8 gray PNG files, not ARIAC camera
images. The cell IDs and the stand-in's answers are chosen for this
example.

Live mode (python3 er_demo.py --live KEY_FILE RAW_DIR IMAGE.png ...,
and er_session.py, which calls ask_live): the scripted server is
removed and nothing else changes. Each image goes to the real model,
and RAW_DIR keeps every request and response, with the key removed.
--live-structured (Run 2, er_rec2.py) adds structured output and
store=False to each call (STRUCTURED) and starts calls GAP_S apart.

Run: python3 er_demo.py   (needs google-genai and jsonschema)
"""

import base64
import hashlib
import json
import struct
import sys
import time
import zlib
from pathlib import Path

import httpx
from google import genai
from google.genai import types
from jsonschema import Draft7Validator

MODEL = "gemini-robotics-er-2-preview"
CELLS = [f"c{n:02d}" for n in range(1, 13)]

PROMPT = (
    "The image shows one battery cell on a conveyor. List each "
    "surface defect: a dent is a round hollow, a scratch is a long "
    "narrow groove, a bulge is a round bump. Answer only with JSON: "
    '{"defective": <true|false>, "defects": [{"type": '
    '<"DENT"|"SCRATCH"|"BULGE">, "point": [y, x]}]}. '
    "The points are in [y, x] format normalized to 0-1000."
)

ANSWER_SCHEMA = {
    "type": "object",
    "required": ["defective", "defects"],
    "additionalProperties": False,
    "properties": {
        "defective": {"type": "boolean"},
        "defects": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["type", "point"],
                "properties": {
                    "type": {"type": "string",
                             "enum": ["DENT", "SCRATCH", "BULGE"]},
                    "point": {
                        "type": "array",
                        "minItems": 2,
                        "maxItems": 2,
                        "items": {"type": "integer",
                                  "minimum": 0, "maximum": 1000},
                    },
                },
            },
        },
    },
}

# The stand-in's scripted answers, one per call, in call order.
NONE = {"defective": False, "defects": []}


def one(kind, y, x):
    return {"defective": True,
            "defects": [{"type": kind, "point": [y, x]}]}


SCRIPT = [
    NONE, one("DENT", 412, 530), NONE, NONE, one("DENT", 388, 471),
    one("BULGE", 455, 602), one("BULGE", 431, 515), NONE,
    one("SCRATCH", 300, 498), one("CRACK", 520, 505),
    one("BULGE", 470, 489), NONE,
]


def placeholder_png():
    """A synthetic 8 x 8 gray PNG (not a camera image)."""
    def chunk(tag, data):
        body = tag + data
        crc = zlib.crc32(body) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + body + struct.pack(
            ">I", crc)
    head = struct.pack(">IIBBBBB", 8, 8, 8, 0, 0, 0, 0)
    rows = b"".join(b"\x00" + bytes([128] * 8) for _ in range(8))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", head)
            + chunk(b"IDAT", zlib.compress(rows))
            + chunk(b"IEND", b""))


class StandIn:
    """Scripted stand-in for the model server (not a real model)."""

    def __init__(self):
        self.requests = []
        self.answers = iter(SCRIPT)

    def __call__(self, request):
        self.requests.append(json.loads(request.content))
        self.method, self.url = request.method, request.url
        text = json.dumps(next(self.answers))
        reply = {"id": f"standin-{len(self.requests)}",
                 "status": "completed",
                 "steps": [{"type": "model_output",
                            "content": [{"type": "text",
                                         "text": text}]}]}
        return httpx.Response(200, json=reply)


def make_client(stand_in):
    mock = httpx.Client(transport=httpx.MockTransport(stand_in))
    options = types.HttpOptions(httpx_client=mock)
    return genai.Client(api_key="no-key-stand-in",
                        http_options=options)


def ask(client, png, **extra):
    response = client.interactions.create(
        model=MODEL,
        input=[
            {"type": "image", "mime_type": "image/png",
             "data": base64.b64encode(png).decode()},
            {"type": "text", "text": PROMPT},
        ],
        generation_config={"thinking_level": "medium"},
        **extra,
    )
    return response.output_text


# Run 2: structured output. https://ai.google.dev/api/interactions-api, read
# 2026-10-18 (Last updated 2026-10-15 UTC): response_format "Enforces that the
# generated response is a JSON object that complies with the JSON schema specified
# in this field"; store: "Whether to store the response and request for later
# retrieval". The structured output page (same date) shows the format below.
# check() still runs on every answer: structured output is a request.
STRUCTURED = {
    "response_format": {"type": "text", "mime_type": "application/json",
                        "schema": ANSWER_SCHEMA},
    "store": False,
}
GAP_S = 13   # s between call starts, chosen: Run 1's 9th call got HTTP
             # 429 ("limit: 5 requests per minute on Free Tier") after 8
             # calls in 34 s; Run 2, 13 s apart, got 12 answers of 12


def check(text):
    """Return (answer, errors): the parsed JSON and schema errors."""
    try:
        answer = json.loads(text)
    except json.JSONDecodeError as err:
        return None, [f"not JSON: {err.msg}"]
    found = Draft7Validator(ANSWER_SCHEMA).iter_errors(answer)
    errors = sorted(
        f"{'.'.join(map(str, e.absolute_path))}: {e.message}"
        for e in found)
    return answer, errors


def ask_all():
    """Ask about every cell; return the stand-in and the answers."""
    stand_in = StandIn()
    client = make_client(stand_in)
    png = placeholder_png()
    results = {}
    for cell in CELLS:
        text = ask(client, png)
        results[cell] = (text,) + check(text)
    return stand_in, results


def show_request(body):
    """Print the request body, image data and prompt shortened."""
    assert set(body) == {"model", "generation_config", "input"}
    print("{")
    print(f'  "model": {json.dumps(body["model"])},')
    config = json.dumps(body["generation_config"])
    print(f'  "generation_config": {config},')
    print('  "input": [')
    for turn in body["input"]:
        assert set(turn) == {"content", "type"}
        print("    {")
        print('     "content": [')
        parts = turn["content"]
        for k, part in enumerate(parts):
            part = dict(part)
            if "data" in part:
                part["data"] = f"<{len(part['data'])} chars>"
            if "text" in part:
                part["text"] = part["text"][:24] + " ..."
            end = "," if k < len(parts) - 1 else ""
            print("      " + json.dumps(part) + end)
        print("     ],")
        print(f'     "type": {json.dumps(turn["type"])}')
        print("    }")
    print("  ]")
    print("}")


def main():
    stand_in, results = ask_all()
    print(f"Requests sent: {len(stand_in.requests)}")
    url = stand_in.url
    print(f"Each one: {stand_in.method} to {url.host}")
    print(f"          path {url.path}")
    show_request(stand_in.requests[0])
    print()
    text, answer, _ = results["c07"]
    print("Raw answer text for c07 (scripted stand-in):")
    print(text)
    print()
    print("Schema check of every answer:")
    for cell, (text, answer, errors) in results.items():
        if errors:
            print(f"  {cell} rejected")
            for error in errors:
                print(f"      {error}")
            continue
        kinds = [d["type"] for d in answer["defects"]] or ["none"]
        print(f"  {cell} valid     defects: {', '.join(kinds)}")
    print()
    print("Mode: offline, scripted stand-in (fixed replies; no model, no key)")


# ---------------------------------------------------------------- live mode

CALL_TIMEOUT_S = 120   # wall s per call, chosen: the robotics page warns that images
                       # and thinking add time; L8's text calls took 0.8 to 1.5 s


class SecondRequest(Exception):
    """The SDK tried to send a call again (a retry). Blocked: no call is repeated."""


class Recorder:
    """httpx event hooks that save every request and response of a live run.

    The files go to raw_dir as LABEL.request.json and LABEL.response.json, with
    the key replaced by <key>. The request keeps everything but the image
    bytes: they are the PNG file next to it, so the request names its SHA-256
    and its length. The response is the body exactly as received.

    One request per label. google-genai 2.31.0 retries an Interactions call
    on 408, 409, 429 and 5XX (_gaos/interactions.py, retry_config), and
    HttpRetryOptions(attempts=0) or attempts=1 still sends 2 requests
    (measured with a mock 503 server, 2026-10-18). A second request for a
    label raises SecondRequest, which the SDK passes on without a retry."""

    def __init__(self, raw_dir, key, image_dir=""):
        self.image_dir = image_dir   # where the PNG files are, if not raw_dir
        self.raw_dir = Path(raw_dir)
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.key = key
        self.label = None
        self.sent = 0
        self.got = 0

    def begin(self, label):
        self.label, self.sent, self.got = label, 0, 0

    def clean(self, text):
        return text.replace(self.key, "<key>") if self.key else text

    def write(self, name, text):
        (self.raw_dir / name).write_text(self.clean(text) + "\n")

    def on_request(self, request):
        self.sent += 1
        if self.sent > 1:
            raise SecondRequest(f"{self.label}: the SDK tried to send the "
                                "call again; no retry is allowed")
        body = json.loads(request.content)
        for turn in body.get("input", []):
            for part in turn.get("content", []):
                if "data" in part:
                    png = base64.b64decode(part["data"])
                    part["data"] = (f"<{len(part['data'])} base64 chars, "
                                    f"sha256 {hashlib.sha256(png).hexdigest()}"
                                    f", the PNG file {self.image_dir}{self.label}.png>")
        headers = {k: ("<key>" if k.lower() == "x-goog-api-key" else v)
                   for k, v in request.headers.items()}
        record = {"method": request.method, "url": str(request.url),
                  "headers": headers, "body": body}
        self.write(f"{self.label}.request.json",
                   json.dumps(record, indent=1, sort_keys=True))

    def on_response(self, response):
        self.got += 1
        response.read()
        self.write(f"{self.label}.response.json", response.text)
        meta = {"status": response.status_code,
                "reason": response.reason_phrase}
        self.write(f"{self.label}.status.json", json.dumps(meta))


def make_live_client(key, recorder, transport=None):
    """The SDK client with no stand-in: a plain httpx client with the
    recorder's hooks. transport is for the tests only (a mock server)."""
    hooks = {"request": [recorder.on_request],
             "response": [recorder.on_response]}
    http = httpx.Client(transport=transport, event_hooks=hooks,
                        timeout=CALL_TIMEOUT_S)
    options = types.HttpOptions(httpx_client=http,
                                timeout=CALL_TIMEOUT_S * 1000)
    return genai.Client(api_key=key, http_options=options)


STOP_STATUS = {400, 401, 403, 404, 429}   # a key, model or quota problem:
                                          # the next calls would fail too


def ask_live(client, recorder, images, log=print, extra=None, gap_s=0):
    """Ask about each image once, in order. images: {label: PNG bytes}.
    extra: more arguments for ask() (Run 2: STRUCTURED). gap_s: the least
    time from one call's start to the next one's (Run 2: GAP_S).

    Returns {label: record}. A record holds the answer text (or the error),
    the schema check, the wall latency and the HTTP status. A failed call is
    kept as it is and never repeated. After a status in STOP_STATUS, or a
    call with no response in CALL_TIMEOUT_S, the other cells are not sent."""
    from gemini_model import _with_deadline   # L8: a wall limit per call

    results = {}
    extra = extra or {}
    last = None
    for label, png in images.items():
        if last is not None:
            time.sleep(max(0.0, last + gap_s - time.monotonic()))
        recorder.begin(label)
        t0 = last = time.monotonic()
        rec = {"text": None, "errors": [], "error": None}
        try:
            rec["text"] = _with_deadline(lambda: ask(client, png, **extra),
                                         CALL_TIMEOUT_S)
        except Exception as err:   # every failure is recorded; no retry
            rec["error"] = recorder.clean(f"{type(err).__name__}: {err}")
        rec["latency_s"] = round(time.monotonic() - t0, 2)
        rec["requests_sent"] = recorder.sent
        status = recorder.raw_dir / f"{label}.status.json"
        rec["http_status"] = (json.loads(status.read_text())["status"]
                              if recorder.got else None)
        if rec["text"] is not None:
            rec["answer"], rec["errors"] = check(rec["text"])
        results[label] = rec
        shown = rec["text"] if rec["error"] is None else rec["error"]
        log(f"{label} ({rec['latency_s']:.2f} s, "
            f"HTTP {rec['http_status']}): {shown}")
        if rec["http_status"] in STOP_STATUS:
            log(f"stop: HTTP {rec['http_status']}; the other cells are "
                "not sent")
            break
        if rec["error"] is not None and rec["error"].startswith("TimeoutError"):
            # The call may still be open: a late response must not be saved
            # under the next cell's label, so no other cell is sent.
            log("stop: no response in time; the other cells are not sent")
            break
    (recorder.raw_dir / "answers.json").write_text(
        recorder.clean(json.dumps(results, indent=1, sort_keys=True)) + "\n")
    return results


def live_main(key_file, raw_dir, paths, structured=False):
    """Students: send your own images with your own key file (mode 600).
    structured: Run 2's request (STRUCTURED) and pacing (GAP_S)."""
    from gemini_model import read_key
    key = read_key(key_file)
    recorder = Recorder(raw_dir, key)
    client = make_live_client(key, recorder)
    images = {Path(p).stem: Path(p).read_bytes() for p in paths}
    if structured:
        ask_live(client, recorder, images, extra=STRUCTURED, gap_s=GAP_S)
    else:
        ask_live(client, recorder, images)


if __name__ == "__main__":
    mode = sys.argv[1:2]
    if mode in (["--live"], ["--live-structured"]) and len(sys.argv) > 4:
        sys.path.insert(0, str(Path(__file__).resolve().parents[2]
                               / "lecture8" / "code"))
        live_main(sys.argv[2], sys.argv[3], sys.argv[4:],
                  structured=mode == ["--live-structured"])
    elif len(sys.argv) == 1:
        main()
    else:
        sys.exit("usage: er_demo.py | er_demo.py --live[-structured] "
                 "KEY_FILE RAW_DIR IMAGE.png ...")
