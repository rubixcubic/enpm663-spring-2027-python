"""L8 demo: an orchestrator loop around an LLM that drives ARIAC through the course skills.

Each step: (1) observe ARIAC, (2) ask the model, (3) check the call in code,
(4) run it through the skills, (5) record the result; repeat until a stop condition.
The model is Gemini (gemini_model.py), or ScriptedModel, a stand-in that returns
fixed replies; a real model's answers vary. The tools are the course skills and
three ARIAC topics (skill_tools.py).

Run (host): run_sim_demo.sh starts ARIAC and the skills server in the container
and runs this file there. Offline, for the exercises: python3 orchestrator.py --fake --runs 2
"""
import argparse
import json
import os

from jsonschema import Draft202012Validator

from gemini_model import MAX_OUTPUT_TOKENS, ModelError, Reply
from skill_tools import EMPTY_TESTER_V, L8_TOOLS

MAX_STEPS = 15     # step limit, chosen well above the recorded Run 1, which took 5 calls (4 skills, then "done")
MAX_INVALID = 2    # invalid outputs in a row, chosen for this example
CELL_MIN, CELL_MAX = 3.4, 3.8   # Li-Ion 3.6 V +/- 0.2 V (CellTypes.msg)

SYSTEM = ("Role: you run the ARIAC inspection cell through the listed tools, one tool call per turn.\n"
          "Facts: robot 1 (inspection_robot_1) catches cells from the conveyor and places them on "
          "voltage tester 1 or 2. Robot 2 (inspection_robot_2) picks a cell from a tester and places "
          "it in an AGV tray slot or drops it in the recycling bin. A Li-Ion cell passes when it reads "
          "3.4 to 3.8 V. After each call you get the tool's result, a fresh observation and the "
          "orchestrator's record.\n"
          "Rules: use only the listed tools. A code other than SUCCESS is a failure: read its message "
          "before the next call. When the goal is reached, reply with the word done and no tool call. "
          "If no action is safe, reply with one sentence that says why.")
GOAL = "Put one Li-Ion cell from the conveyor into agv1 slot 1. Test its voltage on tester 1 first."


def act(name, **args):
    return {"tool": name, "args": args}


# Run 2: the scripted model repeats a call the guard refuses (tester 1 is empty at the start).
RUN2_REPLIES = [act("robot2_pick_from_tester", tester=1)] * 2
# The dry run: the scripted model does the whole task, to time it before a real run.
DRY_REPLIES = [act("robot1_pick_from_conveyor"), act("robot1_place_on_tester", tester=1),
               act("robot2_pick_from_tester", tester=1), act("robot2_place_in_slot", agv=1, slot=1),
               {"text": "done"}]


class ScriptedModel:
    """Stand-in for an LLM: returns the next scripted reply."""

    def __init__(self, replies):
        self.replies = list(replies)

    def __call__(self, system, messages, tools):
        return self.replies.pop(0)


def as_reply(item):
    if isinstance(item, Reply):
        return item
    if "tool" in item:
        return Reply(tool=item["tool"], args=dict(item.get("args", {})))
    return Reply(text=item.get("text", ""))


class Record:
    """The orchestrator's own record: what each robot holds, and each cell's voltage.
    ARIAC publishes no topic for where each cell is (L3), so this record is the only source."""

    def __init__(self):
        self.holding = {"robot1": "NOTHING", "robot2": "NOTHING"}   # a fresh launch; checked in smoke.py
        self.on_tester = {1: None, 2: None}
        self.held_volts = None
        self.slots = {}

    def observe(self, snap):
        for n in (1, 2):
            t = snap["testers"][str(n)]
            if t["status"] != "OPERATIONAL" or t["voltage"] is None:
                continue                           # a malfunction keeps the last reading
            if t["voltage"] < EMPTY_TESTER_V:
                self.on_tester[n] = None
            elif self.on_tester[n] is None:
                self.on_tester[n] = t["voltage"]

    def after(self, name, args, result):
        robot = name.split("_")[0]
        # holding is None when no goal was sent or no result came back (NO_SERVER,
        # REJECTED, TIMEOUT, NO_CELL; skill_tools.SkillTools._failed): keep the known value.
        if robot in self.holding and result.get("holding") is not None:
            self.holding[robot] = result["holding"]
        if result.get("code") != "SUCCESS":
            return
        if name == "robot2_pick_from_tester":
            self.held_volts, self.on_tester[args["tester"]] = self.on_tester[args["tester"]], None
        elif name == "robot2_place_in_slot":
            self.slots[(args["agv"], args["slot"])] = self.held_volts
            self.held_volts = None
        elif name == "robot2_drop_in_recycling":
            self.held_volts = None

    def as_dict(self):
        return {"holding": self.holding,
                "tester_volts": {str(n): v for n, v in self.on_tester.items()},
                "robot2_cell_volts": self.held_volts,
                "slots": {f"agv{a} slot {s}": v for (a, s), v in sorted(self.slots.items())}}


def guard(name, args, snap, rec):
    """Semantic checks before a tool runs, in code. Returns an error text, or None."""
    for robot in ("robot1", "robot2"):
        if name.startswith(robot + "_") and not name.endswith("_move_home"):
            want = "NOTHING" if name in ("robot1_pick_from_conveyor", "robot2_pick_from_tester") else "CELL"
            if rec.holding[robot] != want:
                return f"robot {robot[-1]} holds {rec.holding[robot]}, needs {want}"
    if name == "robot1_pick_from_conveyor" and snap["conveyor"]["status"] == "MALFUNCTIONING":
        return "the conveyor is MALFUNCTIONING"
    if name in ("robot1_place_on_tester", "robot2_pick_from_tester"):
        n = args["tester"]
        t = snap["testers"][str(n)]
        if t["status"] == "MALFUNCTIONING":
            if name == "robot1_place_on_tester":
                return f"tester {n} is MALFUNCTIONING"
            return None   # a pick from it is allowed
        if t["voltage"] is None:
            return f"no reading from tester {n}"
        if name == "robot1_place_on_tester" and t["voltage"] >= EMPTY_TESTER_V:
            return f"tester {n} already holds a cell ({t['voltage']:.2f} V)"
        if name == "robot2_pick_from_tester" and t["voltage"] < EMPTY_TESTER_V:
            return f"tester {n} is empty ({t['voltage']:.2f} V)"
    if name == "robot2_place_in_slot":
        agv, slot = args["agv"], args["slot"]
        a = snap["agvs"][str(agv)]
        if a["station"] != "INSPECTION":
            return f"agv{agv} is at {a['station']}, not INSPECTION"
        if not isinstance(a["slots"], dict):
            return f"no tray reading for agv{agv}"
        if a["slots"][str(slot)]:
            return f"agv{agv} slot {slot} is occupied"
        if rec.held_volts is None:
            return "the held cell has no voltage record"
        if not CELL_MIN <= rec.held_volts <= CELL_MAX:
            return f"the held cell read {rec.held_volts:.2f} V, outside {CELL_MIN} to {CELL_MAX} V"
    return None


def check_call(name, args, decls, snap, rec):
    """The three checks of the Structured Output section, for a tool call: known tool, schema, guard."""
    if name not in decls:
        return f"unknown tool {name!r}"
    errors = list(Draft202012Validator(decls[name]["parameters"]).iter_errors(args))
    if errors:
        return "schema: " + errors[0].message
    return guard(name, args, snap, rec)


def one_cell_in_slot(snap, rec):
    """Goal for Run 1, checked in code: agv1 slot 1 occupied, with a voltage record in the window."""
    slots = snap["agvs"]["1"]["slots"]
    volts = rec.slots.get((1, 1))
    return isinstance(slots, dict) and slots["1"] and volts is not None and CELL_MIN <= volts <= CELL_MAX


def summary(snap, rec):
    t = snap["testers"]
    agv = snap["agvs"]["1"]
    slots = agv["slots"]
    marks = "".join(str(k) if slots[str(k)] else "-" for k in (1, 2, 3, 4)) if isinstance(slots, dict) else "?"

    def tester(n):
        v = t[str(n)]["voltage"]
        return f"tester {n} {'?' if v is None else f'{v:.2f}'} V {t[str(n)]['status']}"
    return (f"t={snap['sim_time_s']:.1f} s | {tester(1)} | {tester(2)} | conveyor "
            f"{snap['conveyor']['status']} | agv1 {agv['station']} slots {marks} | robot 1 "
            f"{rec.holding['robot1']}, robot 2 {rec.holding['robot2']}")


def call_line(step, n_messages, reply):
    if reply.usage:
        u = reply.usage
        return (f"call {step}: {n_messages} messages; {u['input']} in, {u['output']} out tokens; "
                f"{reply.latency_s:.2f} s")
    return f"call {step}: {n_messages} messages; scripted"


def cut_off(reply):
    """The stop reason for a reply with no tool call that did not end normally, else None.

    Gemini thinking docs (gemini_model.parse_raw): at the output cap the reply ends with finish reason
    MAX_TOKENS and holds truncated or no text, so it is not an answer. A scripted
    reply has no finish reason."""
    if reply.tool is not None or reply.finish_reason in (None, "STOP"):
        return None
    if reply.finish_reason == "MAX_TOKENS":
        return (f"model error: reply cut off at the output cap of {MAX_OUTPUT_TOKENS} tokens "
                "(finish reason MAX_TOKENS)")
    return f"model error: reply ended with finish reason {reply.finish_reason}"


def run(model, tools, goal, goal_check, names, max_steps=MAX_STEPS, max_invalid=MAX_INVALID,
        extra_guard=None, record=None, out=print):
    decl_list = tools.declarations(names)
    decls = {d["name"]: d for d in decl_list}
    rec = record if record is not None else Record()
    snap = tools.snapshot()
    rec.observe(snap)
    first = {"goal": goal, "observation": snap, "record": rec.as_dict()}
    messages = [{"role": "user", "text": json.dumps(first), "image_png": None}]
    out(f"goal:   {goal}")
    out(f"obs 0:  {summary(snap, rec)}")
    invalid = 0
    for step in range(1, max_steps + 1):
        try:
            reply = as_reply(model(SYSTEM, messages, decl_list))
        except ModelError as err:
            return f"model error: {err}"
        out(call_line(step, len(messages), reply))
        messages.append({"role": "model", "reply": reply})
        stop = cut_off(reply)
        if stop is not None:
            text = f", text {reply.text!r}" if reply.text else ""
            out(f"  model:  no tool call, finish reason {reply.finish_reason}{text}")
            return stop
        if reply.tool is None:
            out(f"  model:  text {reply.text!r}")
            if goal_check(snap, rec):
                return "goal reached"
            out("  orch:   goal not reached (checked in code)")
            back = {"error": "goal not reached", "observation": snap, "record": rec.as_dict()}
            messages.append({"role": "user", "text": json.dumps(back), "image_png": None})
            continue
        out(f"  model:  {reply.tool}({json.dumps(reply.args)})")
        note = None
        if reply.dropped_calls:
            note = f"ran the first of {reply.dropped_calls + 1} calls; send one call per turn"
            out(f"  orch:   {note}")
        error = check_call(reply.tool, reply.args, decls, snap, rec)
        if error is None and extra_guard is not None:
            error = extra_guard(reply.tool, reply.args, snap, rec)
        if error is not None:
            invalid += 1
            result = {"error": f"refused: {error}"}
            out(f"  orch:   {json.dumps(result)}")
            if invalid == max_invalid:
                return f"{invalid} invalid outputs in a row"
        else:
            invalid = 0
            result = tools.call(reply.tool, reply.args)
            rec.after(reply.tool, reply.args, result)
            out(f"  result: {json.dumps(result)}")
        snap = tools.snapshot()
        rec.observe(snap)
        out(f"obs {step}:  {summary(snap, rec)}")
        response = {"result": result, "observation": snap, "record": rec.as_dict()}
        if note:
            response["note"] = note
        # the id of the call this result answers (Gemini docs, function calling); None for a scripted reply
        messages.append({"role": "tool", "name": reply.tool, "id": reply.call_id, "response": response})
    return "step limit"


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--runs", default="1", help="comma list: 1 (Gemini), 2 (scripted guard), dry (scripted task)")
    p.add_argument("--fake", action="store_true", help="no ARIAC: FakeTools (values chosen for this example)")
    args = p.parse_args(argv)
    if args.fake:
        from fake_tools import FakeTools
        make_tools = FakeTools
    else:
        from sim_session import prepare, ros_node, start_watchdog
        from skill_tools import SkillTools
        start_watchdog()
        node = ros_node("l8_orchestrator")
        prepare(node)
        make_tools = lambda: SkillTools(node)  # noqa: E731
    key_file = os.environ.get("GEMINI_KEY_FILE", "/dev/shm/enpm663_gemini_key")
    for name in args.runs.split(","):
        if name == "1" and not os.path.exists(key_file):
            # with no key file, the scripted model runs instead; the label says so
            print(f"no key file at {key_file}: Run 1 uses the scripted model", flush=True)
            name = "dry"
        if name == "1":
            from gemini_model import GeminiModel
            from gemini_prices import MODEL
            model = GeminiModel(MODEL, key_file, os.environ["DEMO_RAW_DIR"])
            label = f"Gemini, model requested {MODEL}"
        else:
            model = ScriptedModel(RUN2_REPLIES if name == "2" else DRY_REPLIES)
            label = "scripted model: fixed replies"
        print(f"=== Run {name} ({label}) ===", flush=True)
        print("stop:", run(model, make_tools(), GOAL, one_cell_in_slot, L8_TOOLS), flush=True)


if __name__ == "__main__":
    main()
