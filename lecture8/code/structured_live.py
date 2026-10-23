"""L8 demo: one real model output for the Structured Output section, run through validator.check.

The model gets the example system message of the Prompt Structure section, the stub
factory's state (stub_agv.example_factory, chosen for this example) and one tool,
move_agv, whose parameters are validator.SCHEMA. Its call's arguments then go
through the same three checks as the seven scripted outputs.
"""
import json
import os

from gemini_model import GeminiModel
from gemini_prices import MODEL
from stub_agv import example_factory
from validator import SCHEMA, check

SYSTEM = ("Role: you plan the next action for the ARIAC inspection and kitting cell.\n"
          "Facts: three AGVs (agv1 to agv3); stations INSPECTION, ASSEMBLY,\n"
          "SHIPPING, RECYCLING. A Li-Ion kit holds 4 cells; the orchestrator gives\n"
          "you each cell's measured voltage and the window the next cell must fit.\n"
          "Rules: use only the listed tools. Never invent a cell ID. If no action\n"
          "is safe, call no tool and explain why in one sentence.\n"
          "Output: one tool call whose arguments fit the tool's input schema.")
TOOL = {"name": "move_agv", "parameters": SCHEMA,
        "description": "Move one AGV to a station (ARIAC /agvN/move). Only a full tray (4 cells) may go to SHIPPING."}


def main():
    factory = example_factory()
    state = {f"agv{n}": f"{a['station']}, {a['cells']} cells" for n, a in factory.items()}
    user = json.dumps({"goal": "ship the kit on agv1", "state": state})
    model = GeminiModel(MODEL, os.environ["GEMINI_KEY_FILE"], os.environ["DEMO_RAW_DIR"])
    reply = model.ask(SYSTEM, user, tools=[TOOL])
    print(f"user:   {user}")
    if reply.tool is None:
        print(f"model:  text {reply.text!r}\n  -> no tool call")
    else:
        text = json.dumps(reply.args)
        print(f"model:  {reply.tool}({text})\n  -> {check(text, example_factory()) or 'valid'}")
    print(f"tokens: {reply.usage['input']} in, {reply.usage['output']} out; {reply.latency_s:.2f} s")


if __name__ == "__main__":
    main()
