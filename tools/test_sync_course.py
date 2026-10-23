"""Tests for sync_course.py on a temporary layout (no real repos touched)."""
from pathlib import Path

import pytest

import sync_course


def make_layout(tmp_path: Path, manifest: str) -> Path:
    root = tmp_path / "repo"
    (root / "tools").mkdir(parents=True)
    (root / "tools" / "manifest.toml").write_text(manifest)
    (root / "tools" / "course_paths.toml").write_text(
        'slides = "../slides/lectures"\ndocs = "../docs/source/lectures"\n'
    )
    for base in ("slides/lectures", "docs/source/lectures"):
        (tmp_path / base / "lecture2" / "code").mkdir(parents=True)
    (root / "lecture2" / "code").mkdir(parents=True)
    (root / "lecture2" / "code" / "toy.py").write_text("print('toy')\n")
    return root


MANIFEST = '[lecture2]\nboth = ["code/toy.py"]\n'


def test_check_passes_when_copies_match(tmp_path):
    root = make_layout(tmp_path, MANIFEST)
    for base in ("slides/lectures", "docs/source/lectures"):
        (tmp_path / base / "lecture2" / "code" / "toy.py").write_text("print('toy')\n")
    problems, _ = sync_course.check(root)
    assert problems == []


def test_check_reports_drift(tmp_path):
    root = make_layout(tmp_path, MANIFEST)
    (tmp_path / "slides/lectures/lecture2/code/toy.py").write_text("print('toy')\n")
    (tmp_path / "docs/source/lectures/lecture2/code/toy.py").write_text("print('edited')\n")
    problems, _ = sync_course.check(root)
    assert len(problems) == 1 and "docs" in problems[0] and "toy.py" in problems[0]


def test_check_reports_missing_copy(tmp_path):
    root = make_layout(tmp_path, MANIFEST)
    (tmp_path / "slides/lectures/lecture2/code/toy.py").write_text("print('toy')\n")
    problems, _ = sync_course.check(root)
    assert len(problems) == 1 and "missing" in problems[0]


def test_write_overwrites_drift(tmp_path):
    root = make_layout(tmp_path, MANIFEST)
    (tmp_path / "docs/source/lectures/lecture2/code/toy.py").write_text("print('edited')\n")
    written = sync_course.write(root)
    assert len(written) == 2
    for base in ("slides/lectures", "docs/source/lectures"):
        assert (tmp_path / base / "lecture2/code/toy.py").read_text() == "print('toy')\n"
    assert sync_course.check(root)[0] == []


def test_slides_only_entry_skips_docs(tmp_path):
    root = make_layout(tmp_path, '[lecture2]\nslides = ["code/toy.py"]\n')
    sync_course.write(root)
    assert (tmp_path / "slides/lectures/lecture2/code/toy.py").exists()
    assert not (tmp_path / "docs/source/lectures/lecture2/code/toy.py").exists()


def test_unmanaged_files_untouched(tmp_path):
    root = make_layout(tmp_path, MANIFEST)
    ros = tmp_path / "slides/lectures/lecture2/code/ros_demo.py"
    ros.write_text("import rclpy\n")
    sync_course.write(root)
    problems, notes = sync_course.check(root)
    assert problems == []
    assert any("ros_demo.py" in n for n in notes)
    assert ros.read_text() == "import rclpy\n"


def test_missing_source(tmp_path):
    root = make_layout(tmp_path, '[lecture2]\nboth = ["code/nothere.py"]\n')
    with pytest.raises(SystemExit) as err:
        sync_course.write(root)
    assert "nothere.py" in str(err.value)
    assert not (tmp_path / "slides/lectures/lecture2/code/nothere.py").exists()


def test_missing_target_root(tmp_path):
    root = make_layout(tmp_path, MANIFEST)
    (root / "tools" / "course_paths.toml").write_text(
        'slides = "../nowhere/lectures"\ndocs = "../docs/source/lectures"\n'
    )
    with pytest.raises(SystemExit) as err:
        sync_course.check(root)
    assert "nowhere" in str(err.value)


def test_pytest_cache_not_noted(tmp_path):
    root = make_layout(tmp_path, MANIFEST)
    sync_course.write(root)
    cache = tmp_path / "slides/lectures/lecture2/code/tests/.pytest_cache/v/cache"
    cache.mkdir(parents=True)
    (cache / "nodeids").write_text("[]\n")
    _, notes = sync_course.check(root)
    assert not any(".pytest_cache" in n for n in notes)


@pytest.mark.parametrize("rel", ["code/../../outside.txt", "tools/outside.txt", "/tmp/outside.txt"])
def test_entry_outside_code_and_outputs_refused(tmp_path, rel):
    root = make_layout(tmp_path, f'[lecture2]\nboth = ["{rel}"]\n')
    (root / "outside.txt").write_text("outside\n")
    (root / "lecture2" / "tools").mkdir()
    (root / "lecture2" / "tools" / "outside.txt").write_text("outside\n")
    with pytest.raises(SystemExit) as err:
        sync_course.write(root)
    assert rel in str(err.value)
    assert not (tmp_path / "slides/lectures/outside.txt").exists()
    assert not (tmp_path / "slides/lectures/lecture2/tools").exists()


def test_symlink_destination_refused(tmp_path):
    root = make_layout(tmp_path, MANIFEST)
    target = tmp_path / "target.txt"
    target.write_text("keep\n")
    (tmp_path / "slides/lectures/lecture2/code/toy.py").symlink_to(target)
    with pytest.raises(SystemExit) as err:
        sync_course.write(root)
    assert "symlink" in str(err.value) and "toy.py" in str(err.value)
    assert target.read_text() == "keep\n"
    assert not (tmp_path / "docs/source/lectures/lecture2/code/toy.py").exists()


def test_destination_resolving_outside_lecture_refused(tmp_path):
    root = make_layout(tmp_path, MANIFEST)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    code = tmp_path / "slides/lectures/lecture2/code"
    code.rmdir()
    code.symlink_to(elsewhere, target_is_directory=True)
    with pytest.raises(SystemExit) as err:
        sync_course.write(root)
    assert "outside" in str(err.value) and "toy.py" in str(err.value)
    assert not (elsewhere / "toy.py").exists()
