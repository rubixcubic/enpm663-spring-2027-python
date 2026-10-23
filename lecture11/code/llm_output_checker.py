#!/usr/bin/env python3
"""L11 demo: check an LLM's tool call before it reaches a robot, with L8's code.

The tools are the L8 agent's ten (lecture8/code/skill_tools.py): seven
skills of the two inspection robots and three readings. None takes a
cell ID: ARIAC publishes no cell positions (L3), so the orchestrator
keeps its own record of what each robot holds and each cell's voltage.

The checks are L8's check_call() (lecture8/code/orchestrator.py), in its
order:
  1 tool    the name is one of the declared tools
  2 schema  the arguments fit that tool's JSON schema
  3 guard   guard() allows the call in the current state
A call stops at the first check it fails.

The "model" is a scripted stand-in: a fixed list of replies. A real
model's answers vary. The factory is L8's FakeTools (no ARIAC); its
cell voltages and the tester 1 malfunction are chosen for this example.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lecture8" / "code"))
from fake_tools import FakeTools  # noqa: E402
from orchestrator import Record, ScriptedModel, check_call, run  # noqa: E402
from skill_tools import L8_TOOLS  # noqa: E402

# Calls already made before the example (each one passes check_call):
# cell 1 goes through tester 2 into agv1 slot 1, robot 2 picks cell 2
# from tester 2, and robot 1 catches cell 3. Tester 1 is down throughout.
SETUP = [("robot1_pick_from_conveyor", {}),
         ("robot1_place_on_tester", {"tester": 2}),
         ("robot2_pick_from_tester", {"tester": 2}),
         ("robot2_place_in_slot", {"agv": 1, "slot": 1}),
         ("robot1_pick_from_conveyor", {}),
         ("robot1_place_on_tester", {"tester": 2}),
         ("robot2_pick_from_tester", {"tester": 2}),
         ("robot1_pick_from_conveyor", {})]

# Six separate replies of the stand-in model, each checked in that state
REPLIES = {
    "A good call": ("robot2_place_in_slot", {"agv": 1, "slot": 2}),
    "B made-up tool": ("robot1_place_in_slot", {"agv": 1, "slot": 2}),
    "C slot 5": ("robot2_place_in_slot", {"agv": 1, "slot": 5}),
    "D made-up argument": ("robot1_place_on_tester",
                           {"tester": 2, "cell": "c9"}),
    "E full slot": ("robot2_place_in_slot", {"agv": 1, "slot": 1}),
    "F broken tester": ("robot1_place_on_tester", {"tester": 1}),
}
GOAL = "Put the cell robot 2 holds into agv1 slot 2."


def make_state():
    """The fake factory and the orchestrator's record, after SETUP."""
    tools = FakeTools(tester_down={1: (0.0, 1000.0)})
    rec = Record()
    rec.observe(tools.snapshot())
    for name, args in SETUP:
        error = check_call(name, args, DECLS, tools.snapshot(), rec)
        assert error is None, (name, error)
        rec.after(name, args, tools.call(name, args))
        rec.observe(tools.snapshot())
    return tools, rec


def which_check(error):
    """check_call's checks run in order; its text says which one failed."""
    if error.startswith("unknown tool"):
        return "1 (tool)"
    if error.startswith("schema: "):
        return "2"
    return "3 (guard)"


def show(line):
    """Keep run()'s model lines; a result shows its code, a refusal its error."""
    if line.startswith("  result: "):
        print(f"  result: {json.loads(line[10:])['code']}")
    elif line.startswith("  orch:   {"):
        print(f"  orch:   {json.loads(line[10:])['error']}")
    elif line.startswith("  model:"):
        print(line)


def policy(replies):
    """L8's run(): a refused call goes back to the model as its result,
    and MAX_INVALID = 2 refusals in a row end the run. Then fall back."""
    tools, rec = make_state()
    stop = run(ScriptedModel(replies), tools, GOAL,
               lambda snap, rec: snap["agvs"]["1"]["slots"]["2"],
               L8_TOOLS, record=rec, out=show)
    print(f"  stop: {stop}")
    if stop != "goal reached":
        print("  fall back: robot 2 keeps the cell; the GP3 plan"
              " takes the step")


DECLS = {d["name"]: d for d in FakeTools().declarations(L8_TOOLS)}

if __name__ == "__main__":
    tools, rec = make_state()
    snap = tools.snapshot()
    print(f"state: robot 1 holds {rec.holding['robot1']};"
          f" robot 2 holds {rec.holding['robot2']}"
          f" ({rec.held_volts} V)")
    print(f"       agv1 slot 1 occupied;"
          f" tester 1 {snap['testers']['1']['status']}")
    for label, (name, args) in REPLIES.items():
        print(f"{label}: {name}({json.dumps(args)})")
        error = check_call(name, args, DECLS, snap, rec)
        if error is None:
            print("  accepted")
        else:
            print(f"  refused at check {which_check(error)}: {error}")
    print()

    def act(label):
        name, args = REPLIES[label]
        return {"tool": name, "args": args}
    print("Policy run 1: a refused call, then a good one")
    policy([act("C slot 5"), act("A good call"), {"text": "done"}])
    print("Policy run 2: two refused calls in a row")
    policy([act("C slot 5"), act("E full slot")])
