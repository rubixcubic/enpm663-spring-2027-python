"""L8 and L9 demos: the course skills and three ARIAC topics as tools for an LLM agent.

The descriptions are lecture material, not a GP4 starter: GP4 teams write their
own tool descriptions and schemas (GP4 Task 2). Each tool is a declaration in
DECLARATIONS (name, description, JSON Schema of the arguments) and a SkillTools
method with the same name and arguments; tests/test_skill_tools.py checks that
they match.

Sources:
- Skill actions and SkillResult: the course skills package, README "Actions",
  enpm663_skills_interfaces/action/*.action and msg/SkillResult.msg.
- ARIAC 2025 names (branch ariac2025, commit 0c3e722): the comment on each constant.

SkillTools imports ROS when it is created, so this file imports without ROS.
It never prints: the MCP server talks JSON-RPC over stdout, so logs go to the
log callback.
"""
import time
from typing import Callable, Literal

R1 = "/inspection_robot_1/skills"
R2 = "/inspection_robot_2/skills"
VOLTAGE_TOPIC = "/voltage_tester_{n}/voltage"   # voltage_tester_plugin.cpp:67, 84-85
CONVEYOR_TOPIC = "/inspection_conveyor/status"  # linear_conveyor_plugin.cpp:71, 105; model.sdf:149
AGV_INFO_TOPIC = "/agv{n}/info"                 # agv_motion_plugin.cpp:47, 83
TRAY_TOPIC = "/agv{n}/tray_status"              # agv_tray_interface_plugin.cpp:42, 69
BEAM_TOPIC = "/conveyor_beam/change"            # ray_sensor_plugin.cpp:52; NAME conveyor_beam in config/l8_user_config.yaml
FEED_SERVICE = "/inspection_conveyor/cell_feed/control"    # cell_feed_plugin.cpp:95, 139
REPORT_SERVICE = "/inspection_conveyor/inspection/submit"  # physical_inspection_plugin.cpp:95, 110

CODE_NAMES = {0: "SUCCESS", 1: "PLANNING_FAILED", 2: "EXECUTION_FAILED", 3: "GRASP_FAILED",
              4: "PRECONDITION_FAILED", 5: "PLACE_NOT_FOUND", 6: "ZONE_BUSY_TIMEOUT",
              7: "CANCELED"}                                    # SkillResult.msg
HOLDING_NAMES = {0: "NOTHING", 1: "CELL", 2: "SHELL", 3: "MODULE"}  # SkillResult.msg
STATION_NAMES = {1: "INSPECTION", 2: "ASSEMBLY", 3: "SHIPPING", 4: "RECYCLING",
                 -1: "IN_TRANSIT"}                              # AgvStations.msg
STATUS_NAMES = {1: "OPERATIONAL", 2: "MALFUNCTIONING"}          # OperationStates.msg
LI_ION, NO_CELL = 1, 0                                          # CellTypes.msg

# Waits, from the skills package's own tests (sim_tests/scenarios.py), which passed every batch:
EMPTY_TESTER_V = 0.5    # V, chosen in those tests (VOLTAGE_MIN): an empty tester reads 0 V plus noise, a Li-Ion cell about 3.6 V
VOLTAGE_SAMPLES = 10    # readings averaged; the tester adds noise, sd 0.05 V (VOLTAGE_SAMPLES)
TOPIC_WAIT = 10.0       # wall s for one message on a topic (LATEST_WAIT)
GOAL_WAIT = 300.0       # wall s for one skill goal to end (GOAL_WAIT)
BEAM_WAIT = 120.0       # wall s for a fed cell to cross the beam (BEAM_WAIT)
REPORT_TRIES, REPORT_RETRY = 5, 0.5   # report submissions, wall s apart (REPORT_TRIES, REPORT_RETRY)
RTF_FLOOR, WAIT_MARGIN = 0.25, 30.0   # wall budget of a sim-time wait (REALTIME_FACTOR_FLOOR, WALL_LIMIT_MARGIN)


def _args(props=None, required=None):
    return {"type": "object", "properties": props or {}, "required": required or [],
            "additionalProperties": False}


def _int(lo, hi, what):
    return {"type": "integer", "minimum": lo, "maximum": hi, "description": what}


DECLARATIONS = [
    {"name": "robot1_move_home",
     "description": ("Move inspection_robot_1 (robot 1) to its park pose, outside every zone. "
                     "Returns the code and what robot 1 holds."),
     "parameters": _args()},
    {"name": "robot1_pick_from_conveyor",
     "description": ("Feed one Li-Ion cell onto the inspection conveyor and have robot 1 catch it "
                     "as it rides past. Needs robot 1 to hold NOTHING and the conveyor to be "
                     "OPERATIONAL. On SUCCESS robot 1 holds CELL. If the conveyor stops during "
                     "the catch, the code is PRECONDITION_FAILED and robot 1 holds NOTHING."),
     "parameters": _args()},
    {"name": "robot1_place_on_tester",
     "description": ("Robot 1 places the cell it holds on voltage tester 1 or 2, then parks. "
                     "Needs robot 1 to hold CELL. Use an empty tester. On SUCCESS robot 1 holds "
                     "NOTHING; read the testers to get the cell's voltage."),
     "parameters": _args({"tester": _int(1, 2, "voltage tester number")}, ["tester"])},
    {"name": "robot2_move_home",
     "description": ("Move inspection_robot_2 (robot 2) to its park pose, outside every zone. "
                     "Returns the code and what robot 2 holds."),
     "parameters": _args()},
    {"name": "robot2_pick_from_tester",
     "description": ("Robot 2 picks the cell on voltage tester 1 or 2, then parks. Needs robot 2 "
                     "to hold NOTHING. On SUCCESS robot 2 holds CELL. With no cell on the tester "
                     "the code is GRASP_FAILED."),
     "parameters": _args({"tester": _int(1, 2, "voltage tester number")}, ["tester"])},
    {"name": "robot2_place_in_slot",
     "description": (
         "Robot 2 places the cell it holds in one tray slot of an AGV. "
         "Needs robot 2 to hold CELL and the AGV to be at the "
         "INSPECTION station. On SUCCESS robot 2 holds NOTHING. If the "
         "AGV is not there, the code is PRECONDITION_FAILED and robot "
         "2 keeps the cell."),
     "parameters": _args({"agv": _int(1, 3, "AGV number"),
                          "slot": _int(1, 4, "tray slot number")},
                         ["agv", "slot"])},
    {"name": "robot2_drop_in_recycling",
     "description": ("Robot 2 drops the cell it holds in the recycling bin. Needs robot 2 to hold "
                     "CELL. On SUCCESS robot 2 holds NOTHING."),
     "parameters": _args()},
    {"name": "read_testers",
     "description": ("Read both voltage testers: the mean of 10 readings in volts, and the status "
                     "OPERATIONAL or MALFUNCTIONING. An empty tester reads about 0 V. A "
                     "malfunctioning tester reads -1 V whatever it holds."),
     "parameters": _args()},
    {"name": "read_conveyor",
     "description": "Read the inspection conveyor: status OPERATIONAL or MALFUNCTIONING, and speed in m/s.",
     "parameters": _args()},
    {"name": "read_agv",
     "description": "Read one AGV: its station, and whether each of its four tray slots is occupied.",
     "parameters": _args({"agv": _int(1, 3, "AGV number")}, ["agv"])},
    {"name": "wait",
     "description": "Wait a number of simulation seconds without moving any robot, then return.",
     "parameters": _args({"seconds": _int(5, 60, "simulation seconds to wait")}, ["seconds"])},
]
L8_TOOLS = [d["name"] for d in DECLARATIONS if d["name"] != "wait"]
L9_TOOLS = [d["name"] for d in DECLARATIONS]


def summarize_samples(samples):
    """samples: (voltage, status) pairs, oldest first. The status is the newest sample's;
    the voltage is the mean of the samples with that status (a malfunction can start mid-read)."""
    if not samples:
        return {"voltage": None, "status": "NO_READING"}
    status = samples[-1][1]
    same = [v for v, s in samples if s == status]
    return {"voltage": round(sum(same) / len(same), 3),
            "status": STATUS_NAMES.get(status, f"STATUS_{status}")}


def feed_one_cell(start_feed, stop_feed, wait_edge, submit_report, beam_wait=BEAM_WAIT):
    """Feed one cell and submit its passing report, as sim_tests/scenarios.py _feed_one_cell.

    Returns (the beam header or None, a note). The feed is stopped on every path,
    so no second cell follows."""
    try:
        if not start_feed():
            return None, "the cell feed did not start"
        header = wait_edge(beam_wait)
        if header is None:
            return None, f"no cell crossed the beam in {beam_wait:.0f} wall s"
        return header, submit_report()
    finally:
        stop_feed()


class SkillTools:
    """The tools, run against ARIAC and the skills server through rclpy."""

    def __init__(self, node, log: Callable[[str], None] = lambda text: None):
        import rclpy
        from rclpy.action import ActionClient
        from rclpy.qos import qos_profile_sensor_data

        from ariac_interfaces.msg import BreakBeamStatus
        from enpm663_skills_interfaces import action

        self.node, self.log, self._rclpy = node, log, rclpy
        self._ActionClient, self._action = ActionClient, action
        self._clients = {}
        self._edges, self._edge_header = 0, None

        def on_beam(msg):
            if msg.object_detected:
                self._edges += 1
                self._edge_header = msg.header

        node.create_subscription(BreakBeamStatus, BEAM_TOPIC, on_beam, qos_profile_sensor_data)

    # ---------------------------------------------------------------- used by the orchestrator

    def declarations(self, names=None):
        return [d for d in DECLARATIONS if names is None or d["name"] in names]

    def call(self, name, args):
        return getattr(self, name)(**args)

    def snapshot(self):
        return {"sim_time_s": round(self._now(), 1), "testers": self.read_testers(),
                "conveyor": self.read_conveyor(),
                "agvs": {str(n): self.read_agv(n) for n in (1, 2, 3)}}

    # ---------------------------------------------------------------- act tools

    def robot1_move_home(self) -> dict:
        return self._send("MoveHome", f"{R1}/move_home", {})

    def robot1_pick_from_conveyor(self) -> dict:
        mark = self._edges
        header, note = feed_one_cell(lambda: self._feed(LI_ION), lambda: self._feed(NO_CELL),
                                     lambda limit: self._wait_edge(mark, limit), self._submit_report)
        if header is None:
            return self._failed("NO_CELL", note)
        result = self._send("PickFromConveyor", f"{R1}/pick_from_conveyor", {"beam": header})
        result["report"] = note
        return result

    def robot1_place_on_tester(self, tester: Literal[1, 2]) -> dict:
        return self._send("PlaceOnTester", f"{R1}/place_on_tester", {"tester": tester})

    def robot2_move_home(self) -> dict:
        return self._send("MoveHome", f"{R2}/move_home", {})

    def robot2_pick_from_tester(self, tester: Literal[1, 2]) -> dict:
        return self._send("PickFromTester", f"{R2}/pick_from_tester", {"tester": tester})

    def robot2_place_in_slot(self, agv: Literal[1, 2, 3], slot: Literal[1, 2, 3, 4]) -> dict:
        return self._send("PlaceInSlot", f"{R2}/place_in_slot", {"agv": agv, "slot": slot})

    def robot2_drop_in_recycling(self) -> dict:
        return self._send("DropInRecycling", f"{R2}/drop_in_recycling", {})

    # ---------------------------------------------------------------- observe tools

    def read_testers(self) -> dict:
        from ariac_interfaces.msg import VoltageReading
        out = {}
        for n in (1, 2):
            msgs = self._samples(VoltageReading, VOLTAGE_TOPIC.format(n=n), VOLTAGE_SAMPLES)
            out[str(n)] = summarize_samples([(m.voltage, m.operation_status) for m in msgs])
        return out

    def read_conveyor(self) -> dict:
        from ariac_interfaces.msg import ConveyorStatus
        m = self._latest(ConveyorStatus, CONVEYOR_TOPIC)
        if m is None:
            return {"status": "NO_READING", "speed": None}
        return {"status": STATUS_NAMES.get(m.operating_status, f"STATUS_{m.operating_status}"),
                "speed": round(m.speed, 3)}

    def read_agv(self, agv: Literal[1, 2, 3]) -> dict:
        from ariac_interfaces.msg import AgvStatus, AgvTrayStatus
        info = self._latest(AgvStatus, AGV_INFO_TOPIC.format(n=agv))
        tray = self._latest(AgvTrayStatus, TRAY_TOPIC.format(n=agv))
        station = STATION_NAMES.get(info.station_id, str(info.station_id)) if info else "NO_READING"
        slots = ({str(k): bool(getattr(tray, f"slot_{k}_occupied")) for k in (1, 2, 3, 4)}
                 if tray else "NO_READING")
        return {"station": station, "slots": slots}

    def wait(self, seconds: int) -> dict:
        start = self._now()
        self._spin_until(lambda: self._now() >= start + seconds, seconds / RTF_FLOOR + WAIT_MARGIN)
        return {"waited_sim_s": round(self._now() - start, 1)}

    # ---------------------------------------------------------------- helpers

    def _now(self):
        return self.node.get_clock().now().nanoseconds / 1e9

    def _spin_until(self, done, limit):
        give_up = time.monotonic() + limit
        while not done() and time.monotonic() < give_up:
            self._rclpy.spin_once(self.node, timeout_sec=0.05)
        return done()

    def _samples(self, msg_type, topic, count, limit=3 * TOPIC_WAIT):
        got = []
        sub = self.node.create_subscription(msg_type, topic, got.append, 10)
        self._spin_until(lambda: len(got) >= count, limit)
        self.node.destroy_subscription(sub)
        return got[:count]

    def _latest(self, msg_type, topic, limit=TOPIC_WAIT):
        msgs = self._samples(msg_type, topic, 1, limit)
        return msgs[0] if msgs else None

    def _wait_edge(self, mark, limit):
        return self._edge_header if self._spin_until(lambda: self._edges > mark, limit) else None

    def _call(self, srv_type, name, request, limit=10.0):
        client = self.node.create_client(srv_type, name)
        try:
            if not client.wait_for_service(timeout_sec=limit):
                return None
            future = client.call_async(request)
            self._rclpy.spin_until_future_complete(self.node, future, timeout_sec=limit)
            return future.result()
        finally:
            self.node.destroy_client(client)

    def _feed(self, cell_type):
        from ariac_interfaces.srv import ControlCellFeeder
        resp = self._call(ControlCellFeeder, FEED_SERVICE, ControlCellFeeder.Request(cell_type=cell_type))
        return resp is not None and resp.success

    def _submit_report(self):
        """A passing report. Every cell of the demo trials is defect-free (DEFECT_RATE 0.0), and
        ARIAC's door lets only a cell with a passing report reach the catch point (skills README,
        Behaviors)."""
        from ariac_interfaces.msg import InspectionReport
        from ariac_interfaces.srv import SubmitInspectionReport
        answer = "report service not available"
        for _ in range(REPORT_TRIES):
            request = SubmitInspectionReport.Request(report=InspectionReport(passed=True, defects=[]))
            resp = self._call(SubmitInspectionReport, REPORT_SERVICE, request)
            answer = resp.message if resp is not None else "no answer"
            if resp is not None and resp.success:
                break
            time.sleep(REPORT_RETRY)
        return answer

    def _result(self, r, t0, prefix=""):
        return {"code": CODE_NAMES.get(r.code, f"CODE_{r.code}"),
                "holding": HOLDING_NAMES.get(r.holding, f"HOLDING_{r.holding}"),
                "message": prefix + r.message, "attempts": r.attempts,
                "wall_s": round(time.monotonic() - t0, 1)}

    def _failed(self, code, message, t0=None):
        """An act result the skill server did not give, with the same keys as _result.
        holding and attempts are None: no SkillResult came back. wall_s is None when
        no goal was sent (NO_SERVER, NO_CELL), else the wall time since the goal was sent."""
        return {"code": code, "holding": None, "message": message, "attempts": None,
                "wall_s": None if t0 is None else round(time.monotonic() - t0, 1)}

    def _send(self, action_name, server, fields):
        action_type = getattr(self._action, action_name)
        client = self._clients.get(server)
        if client is None:
            client = self._clients[server] = self._ActionClient(self.node, action_type, server)
        if not client.wait_for_server(timeout_sec=30.0):
            return self._failed("NO_SERVER", f"no action server {server}")
        t0 = time.monotonic()
        sent = client.send_goal_async(action_type.Goal(**fields))
        self._rclpy.spin_until_future_complete(self.node, sent, timeout_sec=30.0)
        handle = sent.result()
        if handle is None or not handle.accepted:
            return self._failed("REJECTED", "goal not accepted: the robot runs another goal or is not ready", t0)
        done = handle.get_result_async()
        self._rclpy.spin_until_future_complete(self.node, done, timeout_sec=GOAL_WAIT)
        if done.done():
            return self._result(done.result().result.result, t0)
        self.log(f"{server}: no result in {GOAL_WAIT:.0f} wall s; sending a cancel")
        cancel = handle.cancel_goal_async()
        self._rclpy.spin_until_future_complete(self.node, cancel, timeout_sec=30.0)
        if self._spin_until(done.done, 120.0):   # a cancel retreats and parks first (README, Cancel)
            return self._result(done.result().result.result, t0, f"no result in {GOAL_WAIT:.0f} wall s, canceled: ")
        return self._failed("TIMEOUT", f"no result in {GOAL_WAIT:.0f} wall s, and none after the cancel", t0)
