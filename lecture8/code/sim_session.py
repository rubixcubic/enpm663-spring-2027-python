"""Simulation helpers for the L8 and L9 demos, inside the skills container.

The waits copy the course skills package's test harness (sim_tests/harness.py:
_wait_ready, _start_competition, _wait_skills_ready), and the watchdog copies its
probes (sim_tests/, _start_watchdog): a signal from outside may
not end a call blocked in C, but os._exit from a thread does.

Run: python3 sim_session.py wait-ready   (used by demo_inner.sh)
"""
import os
import sys
import threading
import time

READY_TIMEOUT = 180.0          # wall s for ARIAC to reach READY (harness.py READY_TIMEOUT)
SKILLS_READY_TIMEOUT = 120.0   # wall s for every skills node to say ready (harness.py)
ROBOTS = ("inspection_robot_1", "inspection_robot_2")


def start_watchdog():
    """End this process DEMO_DEADLINE wall s after it starts (set by demo_inner.sh to the limit minus 60 s)."""
    limit = float(os.environ.get("DEMO_DEADLINE", "0") or 0)
    if limit <= 0:
        return

    def fire():
        time.sleep(limit)
        print(f"[watchdog] {limit:.0f} wall s passed; ending the demo", flush=True)
        os._exit(3)
    threading.Thread(target=fire, daemon=True).start()


def ros_node(name):
    import rclpy
    from rclpy.parameter import Parameter
    if not rclpy.ok():
        rclpy.init()
    node = rclpy.create_node(name)
    node.set_parameters([Parameter("use_sim_time", Parameter.Type.BOOL, True)])
    return node


def _spin_until(node, done, limit):
    import rclpy
    give_up = time.monotonic() + limit
    while not done() and time.monotonic() < give_up:
        rclpy.spin_once(node, timeout_sec=0.5)
    return done()


def wait_ready(node, timeout=READY_TIMEOUT):
    from ariac_interfaces.msg import CompetitionStatus
    state = {"ready": False}

    def cb(msg):
        state["ready"] = msg.competition_state >= 1   # READY = 1 (CompetitionStates.msg)
    sub = node.create_subscription(CompetitionStatus, "/competition_status", cb, 10)
    ok = _spin_until(node, lambda: state["ready"], timeout)
    node.destroy_subscription(sub)
    return ok


def start_competition(node):
    import rclpy
    from ariac_interfaces.srv import Trigger
    client = node.create_client(Trigger, "/start_competition")
    if not client.wait_for_service(timeout_sec=30):
        return False
    future = client.call_async(Trigger.Request())
    rclpy.spin_until_future_complete(node, future, timeout_sec=30)
    return future.result() is not None and future.result().success


def wait_skills_ready(node, robots=ROBOTS, timeout=SKILLS_READY_TIMEOUT):
    from rclpy.qos import DurabilityPolicy, QoSProfile
    from std_msgs.msg import Bool
    ready = {r: False for r in robots}
    qos = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL)
    subs = [node.create_subscription(Bool, f"/{r}/skills/ready",
                                     lambda msg, r=r: ready.__setitem__(r, msg.data), qos) for r in robots]
    ok = _spin_until(node, lambda: all(ready.values()), timeout)
    for sub in subs:
        node.destroy_subscription(sub)
    return ok


def prepare(node):
    t0 = time.monotonic()
    if not start_competition(node):
        raise SystemExit("start_competition failed")
    if not wait_skills_ready(node):
        raise SystemExit(f"skills server not ready in {SKILLS_READY_TIMEOUT:.0f} s")
    print(f"competition started; skills ready ({time.monotonic() - t0:.0f} wall s)", flush=True)


if __name__ == "__main__":
    if sys.argv[1:] != ["wait-ready"]:
        sys.exit("usage: sim_session.py wait-ready")
    t0 = time.monotonic()   # demo_inner.sh starts this wait right after it starts the ARIAC launch
    ok = wait_ready(ros_node("demo_wait_ready"))
    print(f"ARIAC READY {time.monotonic() - t0:.0f} wall s after the wait began" if ok
          else f"ARIAC not READY in {READY_TIMEOUT:.0f} s", flush=True)
    sys.exit(0 if ok else 2)
