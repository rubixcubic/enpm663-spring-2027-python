"""score_er.py: the interval arithmetic, set labels, the camera model and a whole fake recording."""
import json
import math

import pytest

import score_er


def test_wilson_interval_known_values():
    lo, hi = score_er.wilson(0, 2)
    assert lo == 0 and hi == pytest.approx(0.6576, abs=1e-4)
    lo, hi = score_er.wilson(3, 3)
    assert lo == pytest.approx(0.4385, abs=1e-4) and hi == 1
    assert score_er.wilson(0, 0) is None


def test_two_defects_on_one_cell_count_for_both_types():
    pred = {"c1": {"BULGE"}, "c2": set(), "c3": {"DENT"}}
    truth = {"c1": {"BULGE", "DENT"}, "c2": set(), "c3": {"SCRATCH"}}
    cells = ["c1", "c2", "c3"]
    assert score_er.set_counts(pred, truth, cells, "BULGE") == (1, 0, 0)
    assert score_er.set_counts(pred, truth, cells, "DENT") == (0, 1, 1)
    assert score_er.set_counts(pred, truth, cells, "SCRATCH") == (0, 0, 1)


def test_the_aim_point_is_the_image_center():
    row, col = score_er.project(0.8, 1.0, 0.457)
    # The config rounds the pose (z 0.5254 to 0.525 m): measured 4 px off, about 0.4 mm.
    assert row == pytest.approx(540, abs=5) and col == pytest.approx(960, abs=1)
    _, col_ahead = score_er.project(0.85, 1.0, 0.457)
    assert col_ahead < 960                      # world +x is the image's left
    row_up, _ = score_er.project(0.8, 1.0, 0.48)
    assert row_up < 540                         # up is the image's top


def test_angle_from_camera():
    assert score_er.angle_from_camera(math.pi / 2) == pytest.approx(0)
    assert score_er.angle_from_camera(-math.pi / 2) == pytest.approx(180)
    assert score_er.angle_from_camera(math.pi / 2 + 2 * math.pi + 0.5) == pytest.approx(math.degrees(0.5))


def test_billed_output_follows_the_totals():
    assert score_er.billed_output(1000, 30, 400, 1430) == 430
    assert score_er.billed_output(1000, 430, 400, 1430) == 430
    with pytest.raises(ValueError):
        score_er.billed_output(1000, 30, 400, 2000)


def test_a_whole_recording(tmp_path, capsys):
    raw = tmp_path / "outputs" / "raw" / "rec"
    raw.mkdir(parents=True)
    (tmp_path / "outputs" / "rec.txt").write_text("date: 2026-10-18 10:00:00 EDT\n")
    caps = [{"cell": f"c0{k}", "ariac_name": f"li-ion_cell_{k - 1}", "cell_x_m": 0.8} for k in (1, 2, 3)]
    (raw / "captures.json").write_text(json.dumps(caps))
    (raw / "cell_info.txt").write_text(
        "Cell li-ion_cell_0:\n\tDefective: True\n\tDefect type: 2\n\tDefects:\n\t - Type: Dent\n"
        "\t   Relative theta: 0.295\n\t   Absolute theta: 1.544\n\t   Z: 0.01424\n"
        "Cell li-ion_cell_1:\n\tDefective: False\n"
        "Cell li-ion_cell_2:\n\tDefective: False\n")
    ans = {"c01": {"text": '{"defective": true, "defects": [{"type": "DENT", "point": [500, 500]}]}',
                   "latency_s": 3.0},
           "c02": {"text": '{"defective": true, "defects": [{"type": "BULGE", "point": [5, 5]}]}',
                   "latency_s": 2.0},
           "c03": {"text": "not json", "latency_s": 1.0}}
    (raw / "answers.json").write_text(json.dumps(ans))
    for c in ("c01", "c02", "c03"):
        (raw / f"{c}.response.json").write_text(json.dumps({
            "model": "gemini-robotics-er-2-preview",
            "usage": {"total_input_tokens": 1000, "total_output_tokens": 30,
                      "total_thought_tokens": 70, "total_tokens": 1100}}))
    score_er.recorded_main(raw)
    out = capsys.readouterr().out
    assert out.startswith("Recorded once, on 2026-10-18, with gemini-robotics-er-2-preview.")
    assert "Cells used: 2 of 3" in out and "c03 rejected by the schema" in out
    assert "DENT: TP 1  FP 0  FN 0" in out and "BULGE: TP 0  FP 1  FN 0" in out
    assert "Any defect (the cell is defective): TP 1  FP 1  FN 0" in out
    # cost per call: 1000 x $1 / 1M + (30 + 70) x $5 / 1M = $0.0015
    assert "all    3000      90      210   3300    6.00  0.004500" in out
    assert "2. No answer had a ```json fence" in out and "fence removed" not in out


def test_strip_fence_removes_only_one_outer_json_fence():
    body = '{"defective": false, "defects": []}'
    assert score_er.strip_fence(f"```json\n{body}\n```") == body
    assert score_er.strip_fence(body) == body
    assert score_er.strip_fence(f"Here: ```json\n{body}\n```") == f"Here: ```json\n{body}\n```"
