"""er_session.py: the cell log parser, the capture timing and the capture loop, without ROS."""
import json
import types

import pytest

import er_session

# A launch log as ARIAC writes it with log_cell_info:=true: gzmsg lines with color codes
# (as in the L8 smoke log), the block format of cheat_tools_plugin.cpp:131-160, and lines
# of other processes in between.
G = "\x1b[1;32m[Msg] \x1b[0m\x1b[1;32m"
E = "\x1b[0m\x1b[1;32m\x1b[0m"
LOG = "\n".join([
    f"[gazebo-1] {G}Gazebo Sim Server v8.10.0{E}",
    f"[gazebo-1] {G}Cell li-ion_cell_0:{E}",
    f"[gazebo-1] {G}\tType: Lithium Ion{E}",
    "[robot_state_publisher-7] [INFO] [1.0] [x]: Robot initialized",
    f"[gazebo-1] {G}\tVoltage: 3.4046{E}",
    f"[gazebo-1] {G}\tRotation: 0.312039{E}",
    f"[gazebo-1] {G}\tDefective: True{E}",
    f"[gazebo-1] {G}\tDefect type: 1{E}",
    f"[gazebo-1] {G}\tDefects:{E}",
    f"[gazebo-1] {G}\t - Type: Bulge{E}",
    f"[gazebo-1] {G}\t   Relative theta: -0.213{E}",
    f"[gazebo-1] {G}\t   Absolute theta: 0.099039{E}",
    f"[gazebo-1] {G}\t   Z: 0.0469{E}",
    f"[gazebo-1] {G}Inspection report correct{E}",
    f"[gazebo-1] {G}Cell li-ion_cell_1:{E}",
    f"[gazebo-1] {G}\tType: Lithium Ion{E}",
    f"[gazebo-1] {G}\tDefective: False{E}",
])


def test_cell_blocks_reads_each_block_and_skips_other_lines():
    blocks = er_session.cell_blocks(LOG)
    assert list(blocks) == ["li-ion_cell_0", "li-ion_cell_1"]
    assert len(blocks["li-ion_cell_0"]) == 10
    assert blocks["li-ion_cell_0"][6] == "\t - Type: Bulge"
    assert blocks["li-ion_cell_1"] == ["\tType: Lithium Ion", "\tDefective: False"]


def test_the_score_parser_reads_what_the_session_writes(tmp_path):
    import score_er
    log = tmp_path / "x_ariac.log"
    log.write_text(LOG)
    er_session.write_cell_info(log, tmp_path, ["li-ion_cell_0", "li-ion_cell_1"], wait_s=0)
    info = score_er.parse_cell_info((tmp_path / "cell_info.txt").read_text())
    assert info["li-ion_cell_0"] == {"defective": True, "set": 1, "defects": [
        {"type": "BULGE", "relative": -0.213, "absolute": 0.099039, "z": 0.0469}]}
    assert info["li-ion_cell_1"] == {"defective": False, "set": None, "defects": []}


def test_a_cell_missing_from_the_log_is_named(tmp_path):
    log = tmp_path / "x_ariac.log"
    log.write_text(LOG)
    missing = er_session.write_cell_info(log, tmp_path, ["li-ion_cell_0", "li-ion_cell_7"], wait_s=0)
    assert missing == ["li-ion_cell_7"]
    assert "(not in the ARIAC log)" in (tmp_path / "cell_info.txt").read_text()


def test_the_image_is_taken_when_the_cell_center_reaches_the_camera():
    assert er_session.DELAY_S == pytest.approx(2.105)
    assert er_session.cell_x_at(10.0, 10.0 + er_session.DELAY_S) == pytest.approx(er_session.CAMERA_X)


class FakeSession:
    """Edges at sim 5, 15, 25 s; images every 1/30 s; spin_until never waits."""

    def __init__(self, edges):
        self.edges = edges
        self.targets = []

    def spin_until(self, done, limit):
        return done()

    def image_after(self, target):
        self.targets.append(target)
        t = (int(target * 30) + 1) / 30
        sec = int(t)
        header = types.SimpleNamespace(stamp=types.SimpleNamespace(sec=sec, nanosec=int((t - sec) * 1e9)))
        return types.SimpleNamespace(header=header, width=4, height=2, encoding="rgb8", step=12,
                                     data=bytes(range(24)))


def test_capture_takes_one_image_per_edge(tmp_path):
    s = FakeSession([5.0, 15.0, 25.0])
    rows = er_session.capture(s, 3, tmp_path)
    assert [r["cell"] for r in rows] == ["c01", "c02", "c03"]
    assert [r["ariac_name"] for r in rows] == ["li-ion_cell_0", "li-ion_cell_1", "li-ion_cell_2"]
    assert s.targets == pytest.approx([5 + 2.105, 15 + 2.105, 25 + 2.105])
    assert all(abs(r["cell_x_m"] - 0.8) < 0.004 for r in rows)   # within one frame (0.1 / 30 m)
    assert (tmp_path / "c03.png").read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_capture_stops_when_no_cell_comes(tmp_path):
    rows = er_session.capture(FakeSession([5.0]), 3, tmp_path)
    assert len(rows) == 1 and not (tmp_path / "c02.png").exists()
