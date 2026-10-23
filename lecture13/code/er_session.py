"""L13 live run: real ARIAC camera images of 12 cells, then one model call per image.

Runs inside the skills container, under L8's demo_inner.sh --no-sim (started by
run_er_session.sh), so the demo's three stops reach every process it starts:
the watchdog at LIMIT - 60 s, timeout's SIGINT at LIMIT, SIGKILL 60 s later.
ARIAC is started here as a child in the demo's own process group (no new session),
so demo_inner.sh's cleanup stops it on every path. No skills server is started.

Steps:
1. Start ARIAC with the trial file, the user config and log_cell_info:=true, which
   prints each cell's defects to the Gazebo log (cheat_tools_plugin.cpp:126-165).
2. Wait for READY, start the competition, start the Li-Ion cell feed.
3. For each of the first N cells: wait for the break beam's rising edge, then save
   the first camera image stamped DELAY_S or more after the edge (the cell is then
   in front of the camera, see config/l13_user_config.yaml).
4. Stop the feed and copy the logged cell blocks out of the ARIAC log (cell_info.txt).
5. With GEMINI_KEY_FILE set: send each image once to the model (er_demo.ask_live).

Writes to DEMO_RAW_DIR: c01.png to cNN.png, captures.json, cell_info.txt, and the
model's raw requests and responses. The ARIAC log goes to DEMO_OUT_DIR.

Run: er_session.py TRIAL USER_CONFIG N   (inside the container, through run_er_session.sh)
"""
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
for n in ("lecture8", "lecture9"):
    sys.path.insert(0, str(HERE.parents[1] / n / "code"))

BEAM_TOPIC = "/conveyor_beam/change"        # ray_sensor_plugin.cpp:52; NAME conveyor_beam
CAMERA_TOPIC = "/er_camera/image"           # image_plugin.cpp:47; NAME er_camera
FEED_SERVICE = "/inspection_conveyor/cell_feed/control"   # cell_feed_plugin.cpp:95, 139
LI_ION, NO_CELL = 1, 0                      # CellTypes.msg
BEAM_X = 0.6        # m, the beam's x (config/l13_user_config.yaml)
CAMERA_X = 0.8      # m, the cell x the camera is aimed at (same file)
CELL_RADIUS = 0.0105   # m, battery_cell/model.sdf collision cylinder
SPEED = 0.1         # m/s, CONVEYOR_SPEED in the user config
# The beam changes when the cell's front reaches x = 0.6, so the cell's center is then
# at 0.6 - 0.0105 = 0.5895 m. It reaches x = 0.8 after (0.8 - 0.5895) / 0.1 = 2.105 s.
DELAY_S = (CAMERA_X - (BEAM_X - CELL_RADIUS)) / SPEED
EDGE_WAIT = 90.0    # wall s for the next cell's edge, chosen: one cell per 10 sim s
                    # (CELL_FEED_RATE 0.1), so 90 s allows a real-time factor down to 0.11
IMAGE_WAIT = 30.0   # wall s for an image stamped after the target time, chosen
ANSI = re.compile(r"\x1b\[[0-9;]*m")


def stamp(header):
    return header.stamp.sec + header.stamp.nanosec / 1e9


def cell_x_at(edge_t, image_t):
    """Where the cell's center is (m) at image_t, if it moves at SPEED after the edge."""
    return BEAM_X - CELL_RADIUS + SPEED * (image_t - edge_t)


BLOCK_KEYS = ("Type:", "Voltage:", "Rotation:", "Defective:", "Defect type:", "Defects:",
              "Relative theta:", "Absolute theta:", "Z:", "Could not find defect type")


def cell_blocks(log_text):
    """The cell blocks that log_cell_info prints, as {cell name: [lines]}.

    Each gzmsg line reads '[gazebo-1] [Msg] <text>', with color codes. A block starts
    at 'Cell <name>:' and holds the [Msg] lines after it whose text starts with one of
    BLOCK_KEYS (cheat_tools_plugin.cpp:131-160; a defect line starts with '- Type:').
    Lines that are not [Msg] lines can come in between (other processes and threads
    write to the same log), so they are skipped; any other [Msg] line ends the block."""
    blocks, current = {}, None
    for raw in log_text.splitlines():
        line = re.sub(r"^\[gazebo-\d+\]\s*", "", ANSI.sub("", raw))
        if not line.startswith("[Msg] "):
            continue
        text = line[len("[Msg] "):].rstrip()
        m = re.fullmatch(r"Cell (\S+):", text.strip())
        if m:
            current = blocks.setdefault(m.group(1), [])
            continue
        body = text.strip()
        body = body[2:] if body.startswith("- ") else body
        if current is not None and body.startswith(BLOCK_KEYS):
            current.append(text)
        else:
            current = None
    return blocks


class Session:
    def __init__(self, node):
        import rclpy
        from rclpy.qos import qos_profile_sensor_data

        from ariac_interfaces.msg import BreakBeamStatus
        self.node, self.rclpy = node, rclpy
        self.edges = []

        def on_beam(msg):
            if msg.object_detected:
                self.edges.append(stamp(msg.header))
        node.create_subscription(BreakBeamStatus, BEAM_TOPIC, on_beam, qos_profile_sensor_data)

    def spin_until(self, done, limit):
        give_up = time.monotonic() + limit
        while not done() and time.monotonic() < give_up:
            self.rclpy.spin_once(self.node, timeout_sec=0.05)
        return done()

    def feed(self, cell_type):
        from ariac_interfaces.srv import ControlCellFeeder
        client = self.node.create_client(ControlCellFeeder, FEED_SERVICE)
        try:
            if not client.wait_for_service(timeout_sec=10.0):
                return "no feed service"
            future = client.call_async(ControlCellFeeder.Request(cell_type=cell_type))
            self.rclpy.spin_until_future_complete(self.node, future, timeout_sec=10.0)
            resp = future.result()
            return "no answer" if resp is None else f"{resp.success}: {resp.message}"
        finally:
            self.node.destroy_client(client)

    def image_after(self, target):
        """The first image on CAMERA_TOPIC stamped at target or later, or None."""
        from rclpy.qos import qos_profile_sensor_data
        from sensor_msgs.msg import Image
        box = []

        def on_image(msg):
            if not box and stamp(msg.header) >= target:
                box.append(msg)
        sub = self.node.create_subscription(Image, CAMERA_TOPIC, on_image, qos_profile_sensor_data)
        self.spin_until(lambda: bool(box), IMAGE_WAIT)
        self.node.destroy_subscription(sub)
        return box[0] if box else None


def capture(session, n, raw_dir):
    from vlm_check import to_png   # L9: sensor_msgs/Image to PNG bytes
    captures = []
    for k in range(1, n + 1):
        label = f"c{k:02d}"
        if not session.spin_until(lambda: len(session.edges) >= k, EDGE_WAIT):
            print(f"{label}: no beam edge in {EDGE_WAIT:.0f} wall s; capture stops", flush=True)
            break
        edge = session.edges[k - 1]
        image = session.image_after(edge + DELAY_S)
        if image is None:
            print(f"{label}: no image in {IMAGE_WAIT:.0f} wall s; capture stops", flush=True)
            break
        t = stamp(image.header)
        (raw_dir / f"{label}.png").write_bytes(to_png(image))
        row = {"cell": label, "ariac_name": f"li-ion_cell_{k - 1}", "edge_sim_s": round(edge, 3),
               "image_sim_s": round(t, 3), "cell_x_m": round(cell_x_at(edge, t), 4),
               "width": image.width, "height": image.height, "encoding": image.encoding}
        captures.append(row)
        print(f"{label}: edge at {edge:.2f} s, image at {t:.2f} s sim, cell center at "
              f"x = {row['cell_x_m']:.3f} m; {image.width} x {image.height} {image.encoding}",
              flush=True)
    return captures


def write_cell_info(log_path, raw_dir, names, wait_s=10.0):
    """Copy the logged block of each captured cell into cell_info.txt, as logged.

    A cell is logged when it spawns, so every captured cell is in the log already;
    the wait covers output that is still in a pipe."""
    give_up = time.monotonic() + wait_s
    while True:
        blocks = cell_blocks(Path(log_path).read_text(errors="replace"))
        missing = [nm for nm in names if not blocks.get(nm)]
        if not missing or time.monotonic() > give_up:
            break
        time.sleep(1.0)
    lines = []
    for nm in names:
        lines.append(f"Cell {nm}:")
        lines += blocks.get(nm, ["\t(not in the ARIAC log)"])
    (raw_dir / "cell_info.txt").write_text("\n".join(lines) + "\n")
    return missing


def main(trial, user, n):
    from sim_session import ros_node, start_competition, start_watchdog, wait_ready
    start_watchdog()
    out_dir = Path(os.environ["DEMO_OUT_DIR"])
    raw_dir = Path(os.environ["DEMO_RAW_DIR"])
    raw_dir.mkdir(parents=True, exist_ok=True)
    log_path = out_dir / f"{out_dir.name}_ariac.log"
    t0 = time.monotonic()
    # No start_new_session: ARIAC stays in this demo's process group (see the docstring).
    launch = subprocess.Popen(
        ["ros2", "launch", "ariac_gz", "ariac.launch.py", f"trial_config:={trial}",
         f"user_config:={user}", "cheat_selection:=0", "headless:=true", "log_cell_info:=true"],
        stdin=subprocess.DEVNULL, stdout=open(log_path, "w"), stderr=subprocess.STDOUT)
    print(f"ARIAC launch started (pid {launch.pid}), log_cell_info:=true", flush=True)
    node = ros_node("er_session")
    if not wait_ready(node):
        print("ARIAC not READY: startup failed", flush=True)
        return 2
    print(f"ARIAC READY {time.monotonic() - t0:.0f} wall s after the launch", flush=True)
    if not start_competition(node):
        print("start_competition failed", flush=True)
        return 2
    session = Session(node)
    print(f"feed Li-Ion: {session.feed(LI_ION)}", flush=True)
    t1 = time.monotonic()
    try:
        captures = capture(session, n, raw_dir)
    finally:
        print(f"feed stop: {session.feed(NO_CELL)}", flush=True)
    print(f"captured {len(captures)} of {n} cells in {time.monotonic() - t1:.0f} wall s", flush=True)
    (raw_dir / "captures.json").write_text(json.dumps(captures, indent=1) + "\n")
    missing = write_cell_info(log_path, raw_dir, [c["ariac_name"] for c in captures])
    print(f"cell_info.txt: {len(captures) - len(missing)} of {len(captures)} cells logged"
          + (f"; missing {', '.join(missing)}" if missing else ""), flush=True)
    key_file = os.environ.get("GEMINI_KEY_FILE")
    if not key_file:
        print("no GEMINI_KEY_FILE: images only, no model call", flush=True)
        return 0 if len(captures) == n else 1
    from er_demo import MODEL, Recorder, ask_live, make_live_client
    from gemini_model import read_key
    key = read_key(key_file)
    recorder = Recorder(raw_dir, key)
    client = make_live_client(key, recorder)
    images = {c["cell"]: (raw_dir / f"{c['cell']}.png").read_bytes() for c in captures}
    print(f"model calls: {MODEL}, one per image, no retry", flush=True)
    results = ask_live(client, recorder, images, log=lambda s: print(s, flush=True))
    print(f"calls answered: {sum(r['error'] is None for r in results.values())} of {len(images)}",
          flush=True)
    return 0 if len(captures) == n else 1


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit("usage: er_session.py TRIAL USER_CONFIG N")
    sys.exit(main(sys.argv[1], sys.argv[2], int(sys.argv[3])))
