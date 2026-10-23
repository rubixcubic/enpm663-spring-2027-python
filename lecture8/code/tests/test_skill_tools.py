"""Tool declarations against their Python methods, and the pure helpers. No ROS needed."""
import ast
import inspect
import pathlib
import types
import typing

import pytest
from jsonschema import Draft202012Validator

import skill_tools
from fake_tools import FakeTools
from skill_tools import (DECLARATIONS, L8_TOOLS, L9_TOOLS, SkillTools, feed_one_cell,
                         summarize_samples)

TOOL_HELPERS = {"declarations", "call", "snapshot"}


def _check_methods(cls):
    for d in DECLARATIONS:
        method = getattr(cls, d["name"])
        params = [p for p in inspect.signature(method).parameters if p != "self"]
        assert params == list(d["parameters"]["properties"]), d["name"]
        assert sorted(d["parameters"]["required"]) == sorted(params), d["name"]
        hints = typing.get_type_hints(method)
        for p in params:
            rule = d["parameters"]["properties"][p]
            assert rule["type"] == "integer", (d["name"], p)
            hint = hints[p]
            if typing.get_origin(hint) is typing.Literal:
                assert list(typing.get_args(hint)) == list(range(rule["minimum"], rule["maximum"] + 1)), (d["name"], p)
            else:
                assert hint is int and "minimum" in rule and "maximum" in rule, (d["name"], p)


def test_every_declaration_has_a_method_with_the_same_arguments():
    _check_methods(SkillTools)


def test_fake_tools_match_the_declarations():
    _check_methods(FakeTools)


def test_no_public_method_without_a_declaration():
    public = {n for n, _ in inspect.getmembers(SkillTools, inspect.isfunction) if not n.startswith("_")}
    assert public - {d["name"] for d in DECLARATIONS} == TOOL_HELPERS


def test_schemas_are_valid_json_schema():
    for d in DECLARATIONS:
        Draft202012Validator.check_schema(d["parameters"])


def test_descriptions_are_plain_text():
    for d in DECLARATIONS:
        text = d["description"]
        assert text and len(text) <= 400, d["name"]   # 400 characters, chosen: one short paragraph
        assert "\u2013" not in text and "\u2014" not in text and "--" not in text, d["name"]


def test_l8_has_no_wait_and_l9_has_every_tool():
    assert "wait" not in L8_TOOLS
    assert L9_TOOLS == [d["name"] for d in DECLARATIONS]


def test_skill_tools_never_prints():
    tree = ast.parse(pathlib.Path(skill_tools.__file__).read_text())
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "print"]
    assert calls == []


def test_summarize_samples_uses_the_newest_status():
    assert summarize_samples([(3.6, 1), (3.62, 1), (-1.0, 2)]) == {"voltage": -1.0, "status": "MALFUNCTIONING"}
    assert summarize_samples([(-1.0, 2), (3.6, 1), (3.62, 1)]) == {"voltage": 3.61, "status": "OPERATIONAL"}
    assert summarize_samples([]) == {"voltage": None, "status": "NO_READING"}


def test_feed_stops_when_no_cell_crosses_the_beam():
    stopped = []
    header, note = feed_one_cell(lambda: True, lambda: stopped.append(1) or True,
                                 lambda limit: None, lambda: "ok", beam_wait=1.0)
    assert header is None and "no cell crossed the beam" in note and stopped == [1]


def test_feed_stops_when_it_never_started():
    stopped = []
    header, note = feed_one_cell(lambda: False, lambda: stopped.append(1) or True,
                                 lambda limit: "H", lambda: "ok")
    assert header is None and note == "the cell feed did not start" and stopped == [1]


def test_feed_returns_the_header_and_the_report_answer():
    stopped = []
    header, note = feed_one_cell(lambda: True, lambda: stopped.append(1) or True,
                                 lambda limit: "H", lambda: "report accepted")
    assert (header, note, stopped) == ("H", "report accepted", [1])


def test_fake_tools_good_path_fills_a_slot():
    f = FakeTools()
    for name, args in [("robot1_pick_from_conveyor", {}), ("robot1_place_on_tester", {"tester": 1})]:
        assert f.call(name, args)["code"] == "SUCCESS"
    assert f.snapshot()["testers"]["1"] == {"voltage": 3.61, "status": "OPERATIONAL"}
    for name, args in [("robot2_pick_from_tester", {"tester": 1}), ("robot2_place_in_slot", {"agv": 1, "slot": 1})]:
        assert f.call(name, args)["code"] == "SUCCESS"
    assert f.snapshot()["agvs"]["1"]["slots"]["1"] is True


def test_fake_tester_malfunction_window():
    f = FakeTools(tester_down={1: (20.0, 60.0)})
    assert f.read_testers()["1"]["status"] == "OPERATIONAL"
    f.wait(30)
    assert f.read_testers()["1"] == {"voltage": -1.0, "status": "MALFUNCTIONING"}
    f.wait(30)
    assert f.read_testers()["1"]["status"] == "OPERATIONAL"


# ---------------------------------------------------------------- act result shape (fix round 1)

ACT_KEYS = {"code", "holding", "message", "attempts", "wall_s"}
ACT_TOOLS = [d for d in DECLARATIONS if d["name"].startswith("robot")]


def _first_args(d):
    return {p: rule["minimum"] for p, rule in d["parameters"]["properties"].items()}


def _assert_act_shape(result, where):
    assert ACT_KEYS <= set(result), (where, sorted(ACT_KEYS - set(result)))
    assert isinstance(result["code"], str) and isinstance(result["message"], str), where
    assert result["holding"] is None or result["holding"] in skill_tools.HOLDING_NAMES.values(), where
    assert result["attempts"] is None or isinstance(result["attempts"], int), where
    assert result["wall_s"] is None or isinstance(result["wall_s"], float), where


def test_fake_act_results_have_the_full_shape():
    for d in ACT_TOOLS:                       # a fresh factory: some tools succeed, some fail
        _assert_act_shape(FakeTools().call(d["name"], _first_args(d)), d["name"])
        failing = FakeTools(fail_once={d["name"]: "EXECUTION_FAILED"})
        _assert_act_shape(failing.call(d["name"], _first_args(d)), (d["name"], "fail_once"))
    _assert_act_shape(FakeTools(cell_volts=()).call("robot1_pick_from_conveyor", {}), "no cells left")
    f = FakeTools()
    for name, args in [("robot1_pick_from_conveyor", {}), ("robot1_place_on_tester", {"tester": 1}),
                       ("robot2_pick_from_tester", {"tester": 1}), ("robot2_place_in_slot", {"agv": 1, "slot": 1}),
                       ("robot1_pick_from_conveyor", {}), ("robot1_place_on_tester", {"tester": 2}),
                       ("robot2_pick_from_tester", {"tester": 2}), ("robot2_drop_in_recycling", {})]:
        result = f.call(name, args)
        assert result["code"] == "SUCCESS", name
        _assert_act_shape(result, name)


def test_fake_fail_once_fails_then_succeeds():
    f = FakeTools(fail_once={"robot1_pick_from_conveyor": "GRASP_FAILED"})
    first = f.call("robot1_pick_from_conveyor", {})
    assert (first["code"], first["holding"]) == ("GRASP_FAILED", "NOTHING")
    second = f.call("robot1_pick_from_conveyor", {})
    assert (second["code"], second["holding"]) == ("SUCCESS", "CELL")
    assert f.calls == [("robot1_pick_from_conveyor", {}), ("robot1_pick_from_conveyor", {})]


def test_fake_fail_once_refuses_a_tool_that_is_not_a_robot_skill():
    for name in ("read_testers", "wait", "robot3_move_home"):
        with pytest.raises(ValueError, match=name):
            FakeTools(fail_once={name: "EXECUTION_FAILED"})


class _Future:
    def __init__(self, value=None, done=True):
        self.value, self.is_done = value, done

    def done(self):
        return self.is_done

    def result(self):
        return self.value if self.is_done else None


def _skill_result(code):
    r = types.SimpleNamespace(code=code, holding=0, message="", attempts=1)
    return types.SimpleNamespace(result=types.SimpleNamespace(result=r))   # GetResult response, then Result


class _Clock:
    """Stands in for skill_tools.time, so the 120 s wait after a cancel passes at once."""

    def __init__(self):
        self.now = 0.0

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class _Rclpy:
    def __init__(self, clock):
        self.clock = clock

    def spin_until_future_complete(self, node, future, timeout_sec=None):
        pass

    def spin_once(self, node, timeout_sec=None):
        self.clock.now += timeout_sec


class _Client:
    """An action client whose server answers in one of six ways (mode)."""

    def __init__(self, mode):
        self.mode = mode

    def wait_for_server(self, timeout_sec=None):
        return self.mode != "no_server"

    def send_goal_async(self, goal):
        if self.mode == "no_handle":
            return _Future(None)
        result = _Future(_skill_result(0), done=self.mode == "success")
        handle = types.SimpleNamespace(accepted=self.mode != "rejected",
                                       get_result_async=lambda: result,
                                       cancel_goal_async=lambda: self._cancel(result))
        return _Future(handle)

    def _cancel(self, result):
        if self.mode == "canceled":
            result.value, result.is_done = _skill_result(7), True   # SkillResult CANCELED = 7
        return _Future(None)


ACTIONS = ("MoveHome", "PickFromConveyor", "PlaceOnTester", "PickFromTester", "PlaceInSlot", "DropInRecycling")


def _ros_free_tools(monkeypatch, mode, feed_ok=True, header="H"):
    clock = _Clock()
    monkeypatch.setattr(skill_tools, "time", clock)
    tools = SkillTools.__new__(SkillTools)          # skips __init__, which imports ROS
    tools.node, tools.log, tools._rclpy = None, lambda text: None, _Rclpy(clock)
    tools._ActionClient = lambda node, action_type, server: _Client(mode)
    tools._action = types.SimpleNamespace(**{a: types.SimpleNamespace(Goal=dict) for a in ACTIONS})
    tools._clients, tools._edges, tools._edge_header = {}, 0, None
    tools._feed = lambda cell_type: feed_ok
    tools._wait_edge = lambda mark, limit: header
    tools._submit_report = lambda: "report accepted"
    return tools


@pytest.mark.parametrize("mode, code", [("success", "SUCCESS"), ("no_server", "NO_SERVER"),
                                        ("no_handle", "REJECTED"), ("rejected", "REJECTED"),
                                        ("canceled", "CANCELED"), ("timeout", "TIMEOUT")])
def test_skill_tools_act_results_have_the_full_shape(monkeypatch, mode, code):
    for d in ACT_TOOLS:
        result = _ros_free_tools(monkeypatch, mode).call(d["name"], _first_args(d))
        assert result["code"] == code, (d["name"], mode)
        _assert_act_shape(result, (d["name"], mode))


@pytest.mark.parametrize("feed_ok, header", [(False, "H"), (True, None)])
def test_skill_tools_no_cell_has_the_full_shape(monkeypatch, feed_ok, header):
    result = _ros_free_tools(monkeypatch, "success", feed_ok, header).call("robot1_pick_from_conveyor", {})
    assert result["code"] == "NO_CELL"
    _assert_act_shape(result, ("NO_CELL", feed_ok, header))
