"""L9 demo: the L8 agent fills agv1's tray while voltage tester 1 malfunctions.

The model is Gemini; --scripted runs a stand-in with fixed replies (the dry run that
times the cycles). Two policies on the same trial file:
  replan: either tester may be used; the run offers no wait tool, so it must replan;
  wait:   tester 1 only (declared so, and a guard in code refuses tester 2); the
          agent waits while tester 1 is MALFUNCTIONING.
The malfunction comes from the trial file (config/l9_trial.yaml); while it lasts the
tester reads -1 V with status MALFUNCTIONING (ARIAC voltage_tester_plugin.cpp:120-131).

Run (host): ./run_sim_demo.sh --name closed_loop_replan_rec1 --sim config/l9_trial.yaml \
            config/l9_user_config.yaml 3600 --key -- closed_loop.py --policy replan --vlm-after
"""
import argparse
import copy
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lecture8" / "code"))
from orchestrator import CELL_MAX, CELL_MIN, Record, ScriptedModel, run  # noqa: E402
from skill_tools import L9_TOOLS  # noqa: E402

MAX_STEPS = 40   # chosen: four cells take 16 skill calls and a "done"; the rest is room for waits and readings
KIT_MIN, KIT_MAX = 14.25, 14.55   # 4 x 3.6 V +/- 0.15 V (CellTypes.msg KIT_VOLTAGE_TOLERANCE)
GOAL = "Fill all four slots of agv1 with Li-Ion cells, each tested on a voltage tester first."
POLICY = {"replan": "Either tester may be used.",
          "wait": "Use tester 1 only. While tester 1 is MALFUNCTIONING, call wait, then read it again."}


def act(name, **args):
    return {"tool": name, "args": args}


DRY_REPLIES = [step for slot in (1, 2, 3, 4) for step in (
    act("robot1_pick_from_conveyor"), act("robot1_place_on_tester", tester=1),
    act("robot2_pick_from_tester", tester=1), act("robot2_place_in_slot", agv=1, slot=slot))] + [{"text": "done"}]


def four_slots(snap, rec):
    """Goal, checked in code: agv1's four slots occupied, each with a voltage in the cell window."""
    slots = snap["agvs"]["1"]["slots"]
    if not isinstance(slots, dict):
        return False
    volts = [rec.slots.get((1, k)) for k in (1, 2, 3, 4)]
    return all(slots[str(k)] for k in (1, 2, 3, 4)) and all(
        v is not None and CELL_MIN <= v <= CELL_MAX for v in volts)


def tool_names(policy):
    """The tools a run offers: replan, every L9 tool but wait; wait, every L9 tool."""
    return [n for n in L9_TOOLS if policy == "wait" or n != "wait"]


def policy_declarations(decls, policy):
    """The declarations a run offers, built from skill_tools.DECLARATIONS (copied, never changed).
    Under wait, each tester parameter is declared as 1 only, and its tool's text says tester 1."""
    decls = copy.deepcopy(decls)
    if policy == "wait":
        for d in decls:
            tester = d["parameters"]["properties"].get("tester")
            if tester is None:
                continue
            tester["minimum"] = tester["maximum"] = 1
            if "voltage tester 1 or 2" not in d["description"]:
                raise ValueError(f"{d['name']}: its description no longer says 'voltage tester 1 or 2'")
            d["description"] = d["description"].replace("voltage tester 1 or 2", "voltage tester 1")
    return decls


class PolicyTools:
    """The tools of one run: the policy's declarations, and the same calls and snapshots.

    on_first_place(args), if given, runs once, at the first snapshot after the first
    successful robot2_place_in_slot (only that cell is in the tray then)."""

    def __init__(self, tools, policy, on_first_place=None):
        self.tools, self.policy = tools, policy
        self.on_first_place, self._placed = on_first_place, None

    def declarations(self, names=None):
        return policy_declarations(self.tools.declarations(names), self.policy)

    def call(self, name, args):
        result = self.tools.call(name, args)
        if (self.on_first_place is not None and name == "robot2_place_in_slot"
                and result.get("code") == "SUCCESS"):
            self._placed = dict(args)
        return result

    def snapshot(self):
        if self._placed is not None:
            hook, args = self.on_first_place, self._placed
            self.on_first_place, self._placed = None, None
            hook(args)
        return self.tools.snapshot()


def policy_guard(policy):
    """The wait policy's backstop, in code. What each check enforces:
    - wait run: its declarations allow tester 1 only, so check_call's schema step refuses
      tester 2 first; this guard refuses any call that names tester 2 again, in case a
      declaration ever loses that limit. The schema keeps wait's seconds in 5 to 60.
    - replan run: no wait tool is declared, so check_call refuses wait as an unknown tool.
    - both runs: orchestrator.guard refuses robot1_place_on_tester on a MALFUNCTIONING
      tester (robot2_pick_from_tester from it is allowed).
    Nothing makes the model wait: two refused calls in a row end the run
    (orchestrator.MAX_INVALID)."""
    def check(name, args, snap, rec):
        if policy == "wait" and args.get("tester") == 2:
            return "policy wait: this run uses tester 1 only"
        return None
    return check


def kit_line(rec):
    """The kit total against ARIAC's window, printed as a fact; the goal checks each cell only."""
    volts = [rec.slots.get((1, k)) for k in (1, 2, 3, 4)]
    if None in volts:
        return "kit total: not every slot has a voltage record"
    total = sum(volts)
    verdict = "inside" if KIT_MIN <= total <= KIT_MAX else "OUTSIDE"
    parts = " + ".join(f"{v:.2f}" for v in volts)
    return f"kit total {total:.2f} V ({parts}); window {KIT_MIN} to {KIT_MAX} V: {verdict}"


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--policy", choices=sorted(POLICY), required=True)
    p.add_argument("--scripted", action="store_true")
    after = p.add_mutually_exclusive_group()
    after.add_argument("--vlm-after", action="store_true", help="then the live VLM check (Gemini)")
    after.add_argument("--image-only", action="store_true", help="then save one camera image, no API call")
    args = p.parse_args(argv)
    if args.scripted and args.vlm_after:
        p.error("--vlm-after calls Gemini; with --scripted, use --image-only")
    from sim_session import prepare, ros_node, start_watchdog
    from skill_tools import SkillTools
    start_watchdog()
    node = ros_node("l9_closed_loop")
    prepare(node)
    model = None
    key_file = os.environ.get("GEMINI_KEY_FILE", "/dev/shm/enpm663_gemini_key")
    if not args.scripted and not os.path.exists(key_file):
        skipped = ", and the live VLM check is skipped" if args.vlm_after else ""
        print(f"no key file at {key_file}: the scripted model runs{skipped}", flush=True)
        args.scripted, args.vlm_after = True, False
    if args.scripted:
        loop_model, label = ScriptedModel(DRY_REPLIES), "scripted model: fixed replies"
    else:
        from gemini_model import GeminiModel
        from gemini_prices import MODEL
        model = GeminiModel(MODEL, key_file, os.environ["DEMO_RAW_DIR"])
        loop_model, label = model, f"Gemini, model requested {MODEL}"
    print(f"=== Closed loop, policy {args.policy} ({label}) ===", flush=True)
    out = Path(os.environ["DEMO_OUT_DIR"])
    import vlm_check   # ROS loads only inside its save_image() and live()

    def first_cell(place):
        # with one cell in the tray, the image shows which way it faces (four look alike)
        print(f"first cell placed (agv{place['agv']} slot {place['slot']}): one image, "
              "to check which way the image faces", flush=True)
        vlm_check.save_image(node, out / "vlm_tray_first_cell.png")
    rec = Record()
    tools = PolicyTools(SkillTools(node), args.policy, on_first_place=first_cell if args.image_only else None)
    stop = run(loop_model, tools, f"{GOAL} {POLICY[args.policy]}", four_slots, tool_names(args.policy),
               max_steps=MAX_STEPS, extra_guard=policy_guard(args.policy), record=rec)
    print("stop:", stop)
    print(kit_line(rec), flush=True)
    record = {"slots": {str(k): rec.slots.get((1, k)) for k in (1, 2, 3, 4)}}
    (out / "record.json").write_text(json.dumps(record, indent=1) + "\n")
    if args.vlm_after and stop.startswith("model error"):
        print("the live VLM check is skipped: the agent loop stopped on a model error; "
              "the camera image is still saved", flush=True)
        args.vlm_after, args.image_only = False, True
    if args.vlm_after or args.image_only:
        vlm_check.live(node, model if args.vlm_after else None, out / "record.json", out / "vlm_tray.png")


if __name__ == "__main__":
    main()
