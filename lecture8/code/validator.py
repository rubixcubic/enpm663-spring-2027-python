"""L8 demo: check an agent's output; retry a bounded number of times.

Each output is the text a model returned. The check has three steps:
parse the JSON, validate it against SCHEMA, then run the semantic
checks a schema cannot express. The retry part uses ScriptedModel, a
stand-in for an LLM that returns fixed replies; a real model's
answers vary.

Run: python3 validator.py   (needs the jsonschema package)
"""

import json

from jsonschema import Draft202012Validator

from orchestrator import ScriptedModel
from stub_agv import PATHS, STATIONS, example_factory

MAX_RETRIES = 2    # chosen for this example: 3 attempts in all

SCHEMA = {
    "type": "object",
    "required": ["agv", "station"],
    "additionalProperties": False,
    "properties": {
        "agv": {"type": "integer", "minimum": 1, "maximum": 3},
        "station": {"enum": list(STATIONS)},
    },
}


def check(text, factory):
    """Return None if the output can run, else the error text."""
    try:
        move = json.loads(text)
    except json.JSONDecodeError as err:
        return f"not JSON: {err.msg}"
    errors = list(Draft202012Validator(SCHEMA).iter_errors(move))
    if errors:
        return "schema: " + errors[0].message
    agv, station = move["agv"], move["station"]
    here, cells = factory[agv]["station"], factory[agv]["cells"]
    if (here, station) not in PATHS:
        return f"semantic: agv{agv} cannot go {here} to {station}"
    if station == "SHIPPING" and cells != 4:
        return f"semantic: agv{agv} holds {cells} of 4 cells"
    return None


def ask(model, factory):
    """Ask, check, and send the error back; give up after the cap."""
    messages = [{"role": "user", "content": "Pick the next move."}]
    for attempt in range(1, MAX_RETRIES + 2):
        text = model("system prompt", messages, [])
        error = check(text, factory)
        print(f"  attempt {attempt}: {text}")
        if error is None:
            return f"accepted {text}"
        if attempt > MAX_RETRIES:
            print(f"    rejected ({error})")
            break
        feedback = f"Rejected ({error}). Return JSON that fits."
        print(f"    sent back: {feedback}")
        messages += [{"role": "assistant", "content": text},
                     {"role": "user", "content": feedback}]
    return "fallback: stop safely, or ask the GP3 planner"


OUTPUTS = [
    '{"agv": 1, "station": "SHIPPING"}',
    '{"agv": 1, "station": SHIPPING}',
    '{"agv": 4, "station": "SHIPPING"}',
    '{"agv": 1, "station": "SHIP"}',
    '{"agv": 1, "station": "SHIPPING", "speed": 2}',
    '{"agv": 2, "station": "SHIPPING"}',
    '{"agv": 3, "station": "SHIPPING"}',
]

if __name__ == "__main__":
    print("=== Seven outputs, one check each ===")
    for text in OUTPUTS:
        error = check(text, example_factory())
        print(f"{text}\n  -> {error or 'valid'}")
    print("=== Bounded retry, run 1 ===")
    model = ScriptedModel([OUTPUTS[3], OUTPUTS[5], OUTPUTS[0]])
    print("  result:", ask(model, example_factory()))
    print("=== Bounded retry, run 2 ===")
    model = ScriptedModel([OUTPUTS[3], OUTPUTS[2], OUTPUTS[5]])
    print("  result:", ask(model, example_factory()))
