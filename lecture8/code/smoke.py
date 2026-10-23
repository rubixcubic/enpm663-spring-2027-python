"""Smoke test before any recording (spec 5): each act tool once, result code checked.

Two cycles: (1) conveyor, tester 1, agv1 slot 1; (2) conveyor, tester 2, recycling.
Also prints each observe tool, the time a snapshot takes, and agv1's four slot frames
from TF (the L9 camera is placed from them)."""
import sys
import time

from sim_session import prepare, ros_node, start_watchdog
from skill_tools import SkillTools

STEPS = [("robot1_move_home", {}), ("robot2_move_home", {}),
         ("robot1_pick_from_conveyor", {}), ("robot1_place_on_tester", {"tester": 1}),
         ("robot2_pick_from_tester", {"tester": 1}), ("robot2_place_in_slot", {"agv": 1, "slot": 1}),
         ("robot1_pick_from_conveyor", {}), ("robot1_place_on_tester", {"tester": 2}),
         ("robot2_pick_from_tester", {"tester": 2}), ("robot2_drop_in_recycling", {})]


def slot_frames(node):
    import rclpy
    from rclpy.time import Time
    from tf2_ros import Buffer, TransformListener
    buf = Buffer()
    TransformListener(buf, node)
    end = time.monotonic() + 10.0
    while time.monotonic() < end:
        rclpy.spin_once(node, timeout_sec=0.1)
    for k in (1, 2, 3, 4):
        try:
            t = buf.lookup_transform("world", f"agv1_slot{k}_frame", Time()).transform.translation
            print(f"agv1_slot{k}_frame in world: ({t.x:.4f}, {t.y:.4f}, {t.z:.4f}) m")
        except Exception as err:   # report and go on: the act results above still count
            print(f"agv1_slot{k}_frame: no transform from world ({type(err).__name__}: {err})")
    try:   # which frame is the TF root (the L9 camera pose is given in world)
        import yaml
        frames = yaml.safe_load(buf.all_frames_as_yaml())   # '[]' when the buffer is empty
        parents = {k: v["parent"] for k, v in frames.items()} if isinstance(frames, dict) else {}
        chain = ["agv1_slot1_frame"]
        while chain[-1] in parents and len(chain) < 20:
            chain.append(parents[chain[-1]])
        print(f"TF chain: {' <- '.join(chain)} (root {chain[-1]})")
    except Exception as err:
        print(f"TF chain: not read ({type(err).__name__}: {err})")


def main():
    start_watchdog()
    node = ros_node("l8_smoke")
    prepare(node)
    tools = SkillTools(node, log=lambda text: print(text, file=sys.stderr))
    t0 = time.monotonic()
    snap = tools.snapshot()
    print(f"snapshot took {time.monotonic() - t0:.1f} wall s: {snap}")
    failed = 0
    for name, args in STEPS:
        # The result's wall_s counts the goal only; this time also counts the cell feed.
        t1 = time.monotonic()
        result = tools.call(name, args)
        print(f"{name}({args}) [{time.monotonic() - t1:.1f} wall s]: {result}")
        failed += result.get("code") != "SUCCESS"
    print(f"read_testers: {tools.read_testers()}")
    print(f"read_conveyor: {tools.read_conveyor()}")
    print(f"read_agv(1): {tools.read_agv(1)}")
    slot_frames(node)
    print(f"smoke: {len(STEPS) - failed} of {len(STEPS)} act calls SUCCESS")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
