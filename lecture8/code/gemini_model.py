"""L8 and L9 demos: a thin Gemini client with the same interface as ScriptedModel.

model(system, messages, tools) -> Reply. The key is read from a file (mode 600)
and never printed, logged or saved: every error text and every saved response
has it replaced by <key>. Each API response is saved as JSON in raw_dir, with the
latency measured here next to it (the response carries none), so every number on
a slide traces back to a response.

SDK details come from the Gemini API docs; each function below names the page
and the date read. The SDK is imported only in _make_client, so the tests and
the host tools (run_cost.py, run_sim_demo.sh) run without it.

Run: python3 gemini_model.py --probe OUT_DIR   (records the test fixtures; needs the key)
     python3 gemini_model.py --reported-model RAW_DIR
"""
import json
import stat
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

CALL_TIMEOUT_S = 60   # wall s per API call, chosen: well above the 0.81 to 1.52 s the probe measured (2026-10-17)
MAX_OUTPUT_TOKENS = 1000   # per call, thinking included; chosen: the course's cost estimate assumes this cap
NOT_RUN = "not run: the orchestrator runs only the first call of a turn; send one call per turn"


@dataclass
class Reply:
    tool: str | None = None
    args: dict | None = None
    text: str | None = None
    dropped_calls: int = 0
    usage: dict | None = None
    latency_s: float | None = None
    model_version: str | None = None
    raw_content: object = field(default=None, repr=False)
    call_id: str | None = None   # the id of the call in tool; its result must carry it (Gemini docs, function calling)
    dropped: list = field(default_factory=list)   # {"name", "id"} of each call after the first
    finish_reason: str | None = None   # why the reply ended: STOP, or MAX_TOKENS at the output cap (Gemini docs, thinking)


class ModelError(Exception):
    """An API error or timeout. The run ends with this as its logged reason; no retry."""


def read_key(path):
    p = Path(path)
    try:
        mode = stat.S_IMODE(p.stat().st_mode)
    except FileNotFoundError:
        raise ModelError(f"no key file at {path}") from None
    if mode & 0o077:
        raise ModelError(f"key file {path} must be mode 600, not {mode:o}")
    key = p.read_text().strip()
    if not key:
        raise ModelError(f"key file {path} is empty")
    return key


class GeminiModel:
    def __init__(self, model_name, key_path, raw_dir, client=None):
        self.model_name = model_name
        self.raw_dir = Path(raw_dir)
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.calls = 0
        self._key = None
        if client is None:
            self._key = read_key(key_path)
            client = _make_client(self._key, CALL_TIMEOUT_S)
        self._client = client

    def __repr__(self):
        return f"GeminiModel({self.model_name!r})"

    def _clean(self, text):
        return text.replace(self._key, "<key>") if self._key else text

    def __call__(self, system, messages, tools):
        return self._send(build_request(self.model_name, system, messages, tools))

    def ask(self, system, text, image_png=None, tools=None):
        message = {"role": "user", "text": text, "image_png": image_png}
        return self._send(build_request(self.model_name, system, [message], tools or []))

    def _send(self, request):
        self.calls += 1
        t0 = time.monotonic()
        try:
            response = _with_deadline(lambda: send_request(self._client, request), CALL_TIMEOUT_S)
        except Exception as err:   # every SDK and network error ends the run, with no retry
            raise ModelError(self._clean(f"call {self.calls}: {type(err).__name__}: {err}")) from None
        latency = time.monotonic() - t0
        raw = dump_response(response)
        text = self._clean(json.dumps(raw, indent=1, sort_keys=True))
        (self.raw_dir / f"call_{self.calls:03d}.json").write_text(text + "\n")
        meta = {"latency_s": round(latency, 3), "model_requested": self.model_name}
        (self.raw_dir / f"call_{self.calls:03d}.meta.json").write_text(json.dumps(meta) + "\n")
        reply = parse_raw(json.loads(text))
        reply.latency_s = round(latency, 2)
        reply.raw_content = model_content(response)
        return reply


def _with_deadline(fn, limit_s):
    """Run fn() and return its value, or raise TimeoutError after limit_s wall seconds.

    The SDK's timeout is httpx's limit for each step of a request (connect, read,
    write, pool), not one limit for the whole call (python-genai docs), so a slow reply could last
    longer. fn runs in a daemon thread: after the deadline it is left to end on the
    httpx timeout, and it never keeps the program from exiting. An exception from
    fn, such as httpx.TimeoutException or errors.APIError (python-genai docs), is raised here."""
    box = {}

    def run():
        try:
            box["value"] = fn()
        except BaseException as err:   # handed to the caller below
            box["error"] = err

    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    worker.join(limit_s)
    if worker.is_alive():
        raise TimeoutError(f"no response in {limit_s:g} wall s")
    if "error" in box:
        raise box["error"]
    return box.get("value")


# ---------------------------------------------------------------- the SDK side (Gemini API and python-genai docs)

def _make_client(key, timeout_s):
    """An SDK client that sends key and gives up on a request step after timeout_s.

    https://ai.google.dev/gemini-api/docs/api-key, read 2026-10-17: the key goes
    to genai.Client(api_key=...); the SDK sends it in the x-goog-api-key header.
    https://googleapis.github.io/python-genai/genai.html, read 2026-10-17:
    HttpOptions.timeout is in milliseconds. It is httpx's per-step timeout, so
    GeminiModel._send adds the wall-clock limit (_with_deadline).
    Same page: HttpRetryOptions.attempts "If 0 or 1, it means no retries".
    Built-in retries are turned off: attempts=1 makes that explicit (with no retry
    options the SDK also makes one attempt, SDK source _api_client.py retry_args)."""
    from google import genai
    from google.genai import types
    options = types.HttpOptions(timeout=int(timeout_s * 1000),
                                retry_options=types.HttpRetryOptions(attempts=1))
    return genai.Client(api_key=key, http_options=options)


# https://ai.google.dev/api/generate-content (Schema), read 2026-10-17: the fields of the
# OpenAPI Schema subset that `parameters` takes. additionalProperties is not one of them.
SUPPORTED_KEYS = {"type", "format", "title", "description", "nullable", "enum", "maxItems",
                  "minItems", "properties", "required", "minProperties", "maxProperties",
                  "minLength", "maxLength", "pattern", "example", "anyOf", "propertyOrdering",
                  "default", "items", "minimum", "maximum"}


def to_declaration(decl):
    """One DECLARATIONS entry in the API's format.

    https://ai.google.dev/api/generate-content, read 2026-10-17: name and
    description, and parameters as the Schema subset (SUPPORTED_KEYS). Every other
    keyword, such as additionalProperties, is dropped here; skill_tools.py keeps it
    because check_call() validates every call against the full schema. type is
    required, and enum is "for Type.STRING", so an enum with no type gets
    "type": "string" when all its values are strings, and any other enum is refused."""
    out = {"name": decl["name"], "description": decl["description"]}
    if "parameters" in decl:
        out["parameters"] = _schema(decl["parameters"], decl["name"])
    return out


def _schema(node, where):
    out = {k: v for k, v in node.items() if k in SUPPORTED_KEYS}
    if "properties" in out:
        out["properties"] = {k: _schema(v, f"{where}.{k}") for k, v in out["properties"].items()}
    if "items" in out:
        out["items"] = _schema(out["items"], f"{where}[]")
    if "anyOf" in out:
        out["anyOf"] = [_schema(s, where) for s in out["anyOf"]]
    if "enum" in out:
        if not all(isinstance(v, str) for v in out["enum"]):
            raise ValueError(f"{where}: the Gemini API allows an enum in function parameters for strings only")
        out.setdefault("type", "string")
    return out


def build_request(model_name, system, messages, tools):
    """{"model", "contents", "config"} as plain dicts, from the neutral messages.

    https://googleapis.github.io/python-genai/, read 2026-10-17: every SDK method
    takes plain dicts. Config fields from GenerateContentConfigDict, same site.
    https://ai.google.dev/gemini-api/docs/generate-content/function-calling
    and .../thought-signatures, read 2026-10-17: a model turn goes back unchanged
    (raw_content, with its thought signatures), and each function result carries the
    exact id of the call it answers, in a content with role "user". A tool message
    may give that id as "id"; with no "id", the id of the call in the model turn
    before it is used. Each dropped call gets an answer too, with an error saying it
    was not run, so every call id in the model turn has its result.
    Same function-calling page: AUTO is the default mode with function
    declarations only; it is set here to make it explicit. Automatic function
    calling is off, so the SDK never runs a tool.
    https://ai.google.dev/gemini-api/docs/generate-content/image-understanding,
    read 2026-10-17: a PNG goes inline as bytes, before the text.
    https://ai.google.dev/gemini-api/docs/generate-content/thinking, read
    2026-10-17: max_output_tokens counts thinking tokens and is a hard cutoff."""
    contents = []
    last = None   # the Reply of the model turn whose calls still need results
    for m in messages:
        if m["role"] == "user":
            parts = []
            if m.get("image_png"):
                parts.append({"inline_data": {"mime_type": "image/png", "data": m["image_png"]}})
            parts.append({"text": m["text"]})
            contents.append({"role": "user", "parts": parts})
        elif m["role"] == "model":
            last = m["reply"]
            contents.append(last.raw_content if last.raw_content is not None else _rebuild(last))
        elif m["role"] == "tool":
            call_id = m.get("id", last.call_id if last is not None else None)
            parts = [_function_response(m["name"], m["response"], call_id)]
            for d in (last.dropped if last is not None else []):
                parts.append(_function_response(d["name"], {"error": NOT_RUN}, d["id"]))
            contents.append({"role": "user", "parts": parts})
            last = None
        else:
            raise ValueError(f"unknown message role {m['role']!r}")
    config = {"max_output_tokens": MAX_OUTPUT_TOKENS, "automatic_function_calling": {"disable": True}}
    if system:
        config["system_instruction"] = system
    if tools:
        config["tools"] = [{"function_declarations": [to_declaration(d) for d in tools]}]
        config["tool_config"] = {"function_calling_config": {"mode": "AUTO"}}
    return {"model": model_name, "contents": contents, "config": config}


def _function_response(name, response, call_id):
    part = {"name": name, "response": response}
    if call_id is not None:
        part["id"] = call_id
    return {"function_response": part}


def _rebuild(reply):
    """A model turn from a Reply with no raw_content (a scripted reply). It has no
    thought signature, which a Gemini 3 model needs on its first call (Gemini docs, thought signatures)."""
    if reply.tool is not None:
        call = {"name": reply.tool, "args": reply.args or {}}
        if reply.call_id is not None:
            call["id"] = reply.call_id
        return {"role": "model", "parts": [{"function_call": call}]}
    return {"role": "model", "parts": [{"text": reply.text or ""}]}


def send_request(client, request):
    """One generateContent call. Source: https://ai.google.dev/gemini-api/docs/generate-content/function-calling,
    read 2026-10-17: client.models.generate_content(model=..., contents=..., config=...)."""
    return client.models.generate_content(model=request["model"], contents=request["contents"],
                                          config=request["config"])


def dump_response(response):
    """The response as JSON-ready data. Not in the docs; SDK source _common.py
    (v2.31.0) lines 661 to 662, to_json_dict() = model_dump(exclude_none=True,
    mode='json'), so bytes such as thought signatures come out as base64 text."""
    return response.to_json_dict()


def model_content(response):
    """The model turn to send back unchanged. Source: https://ai.google.dev/gemini-api/docs/generate-content/function-calling,
    read 2026-10-17: contents.append(response.candidates[0].content)."""
    candidates = response.candidates
    return candidates[0].content if candidates else None


# ---------------------------------------------------------------- readers of the dumped JSON (no SDK)

def _get(d, snake, camel):
    """A field under its SDK name (snake_case, written by to_json_dict) or its REST name."""
    if not isinstance(d, dict):
        return None
    return d[snake] if snake in d else d.get(camel)


def parse_raw(raw):
    """A Reply from one dumped response.

    https://ai.google.dev/gemini-api/docs/generate-content/function-calling, read
    2026-10-17: "always iterate through the parts array rather than relying on
    position". The first function call is the tool; each further call is dropped and
    counted. Text parts are joined, leaving out thought parts (parts with thought: true, same page).
    https://ai.google.dev/gemini-api/docs/generate-content/thinking, read 2026-10-17:
    at the max_output_tokens cap the model "stops generating with finish_reason:
    MAX_TOKENS and returns truncated or empty output", so the finish reason is kept:
    with no call and no text, it tells a cut-off reply from an empty answer."""
    candidates = _get(raw, "candidates", "candidates") or []
    content = _get(candidates[0], "content", "content") if candidates else None
    parts = _get(content, "parts", "parts") or []
    calls = [c for c in (_get(p, "function_call", "functionCall") for p in parts) if c]
    texts = [p["text"] for p in parts if p.get("text") and not p.get("thought")]
    reply = Reply(text="".join(texts) or None, usage=usage_from_raw(raw),
                  model_version=model_from_raw(raw),
                  finish_reason=_get(candidates[0], "finish_reason", "finishReason") if candidates else None)
    if calls:
        reply.tool, reply.args, reply.call_id = calls[0]["name"], calls[0].get("args") or {}, calls[0].get("id")
        reply.dropped = [{"name": c["name"], "id": c.get("id")} for c in calls[1:]]
        reply.dropped_calls = len(reply.dropped)
    return reply


def usage_from_raw(raw):
    """Token counts, None where a field is absent. Source: https://ai.google.dev/gemini-api/docs/generate-content/tokens,
    read 2026-10-17: prompt_token_count (input), candidates_token_count (output),
    thoughts_token_count (thinking), total_token_count."""
    u = _get(raw, "usage_metadata", "usageMetadata") or {}
    return {"input": _get(u, "prompt_token_count", "promptTokenCount"),
            "output": _get(u, "candidates_token_count", "candidatesTokenCount"),
            "thoughts": _get(u, "thoughts_token_count", "thoughtsTokenCount"),
            "total": _get(u, "total_token_count", "totalTokenCount")}


def model_from_raw(raw):
    """Source: https://ai.google.dev/api/generate-content, read 2026-10-17: modelVersion,
    "The model version used to generate the response"."""
    return _get(raw, "model_version", "modelVersion")


def billed_output(usage):
    """Output tokens billed at the output price. Source: https://ai.google.dev/gemini-api/docs/generate-content/tokens,
    read 2026-10-17: "response pricing is the sum of output tokens and thinking tokens",
    and candidates_token_count leaves the thoughts out, so both are added."""
    return (usage["output"] or 0) + (usage["thoughts"] or 0)


# ---------------------------------------------------------------- command line

def _probe(out_dir, model_name, key_path):
    """Record the three test fixtures: a function call, a reply to its result, an image answer."""
    import io

    from PIL import Image

    from skill_tools import DECLARATIONS
    out = Path(out_dir)
    model = GeminiModel(model_name, key_path, out / "raw")
    home = [d for d in DECLARATIONS if d["name"] == "robot2_move_home"]
    first = model.ask("You control a robot cell through tools.", "Send robot 2 to its park pose.", tools=home)
    history = [{"role": "user", "text": "Send robot 2 to its park pose.", "image_png": None},
               {"role": "model", "reply": first},
               {"role": "tool", "name": "robot2_move_home", "id": first.call_id,
                "response": {"result": {"code": "SUCCESS", "holding": "NOTHING", "message": "parked"}}}]
    model("You control a robot cell through tools.", history, home)
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), (200, 30, 30)).save(buf, "PNG")   # a red square, chosen for the probe
    model.ask("", "What color is this image? Answer in one word.", image_png=buf.getvalue())
    for n, name in ((1, "function_call"), (2, "tool_reply"), (3, "image_reply")):
        (out / f"{name}.json").write_text((out / "raw" / f"call_{n:03d}.json").read_text())
    print(f"wrote 3 fixtures to {out}; {model.calls} calls")


if __name__ == "__main__":
    if sys.argv[1:2] == ["--probe"]:
        import os

        from gemini_prices import MODEL
        _probe(sys.argv[2], MODEL, os.environ["GEMINI_KEY_FILE"])
    elif sys.argv[1:2] == ["--reported-model"]:
        files = sorted(Path(sys.argv[2]).glob("call_*[0-9].json"))
        print(model_from_raw(json.loads(files[0].read_text())) if files else "none (no API call)")
    else:
        sys.exit("usage: gemini_model.py --probe OUT_DIR | --reported-model RAW_DIR")
