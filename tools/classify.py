"""Decide, by reading each lecture script's imports, which ones import without
ROS 2, and write tools/manifest.toml. It never runs a lecture script.

    env -i HOME=$HOME PATH=$HOME/.local/bin:/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 uv run python tools/classify.py

For each script, this reads its module-level imports with ast: an import inside a
function, a lambda or a class method does not count, since that code only runs when
the function is called, not when the file is imported. An import inside a try block
that catches ImportError or ModuleNotFoundError is optional: a missing optional name
never fails the script.

A name is local when it is one of the lecture's own files: <name>.py or a package
folder <name>/__init__.py, found first in the script's own folder, then (for a
script under code/tests/) in the lecture's code/ folder, then, when the script's
source text contains the string "lecture8", in SLIDES/lecture8/code. A local name is
read and analysed the same way, and its own missing names count for the script that
imported it. Any other name is looked up with importlib.util.find_spec in this
process, which runs with no ROS 2 on its path (env -i), so a ROS 2 package is always
missing here; a standard library name is looked up the same way and is always found.

A script is managed when nothing it needs, other than an optional name, is missing.
It is ROS when every missing name is a ROS 2 package (see ROS below). It is excluded
when every missing name that is not a ROS 2 package is in EXCLUDED: a name this
project cannot install next to its pins (mcp needs a newer jsonschema than the one
this project pins). Anything else is an error: a missing name that is not ROS 2 and
not excluded.

Each lecture's outputs are managed when a managed script writes them (named in the
lecture's run_all.sh) or when the docs repo already copies them. Files the docs
repo has no copy of go to "slides" only. classification.txt gets one line per
script: lecture, path, kind (managed, ROS, error or excluded), and the detail (the
missing names, "ok" for managed, or the excluded reason).

RUNTIME_ROS overrides this reading for a script that needs ROS 2 only because of
something it does when it runs, not because of what it imports: it always gets the
verdict ROS, with its own reason, no matter what its imports say.
"""
import ast
import importlib.util
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
paths = tomllib.loads((ROOT / "tools" / "course_paths.toml").read_text())
SLIDES = (ROOT / paths["slides"]).resolve()
DOCS = (ROOT / paths["docs"]).resolve()
DATA = {".yaml", ".yml", ".csv", ".pddl", ".json", ".txt"}

# ROS 2 packages: a script missing only these is "ROS", not "error".
ROS = {
    "rclpy", "rosidl_runtime_py", "rosidl_parser", "ariac_interfaces", "py_trees_ros",
    "sensor_msgs", "sensor_msgs_py", "geometry_msgs", "std_msgs", "std_srvs",
    "builtin_interfaces", "tf2_ros", "tf2_geometry_msgs", "tf_transformations",
    "launch", "launch_ros", "launch_testing", "ament_index_python", "rcl_interfaces",
    "action_msgs", "unique_identifier_msgs", "message_filters", "cv_bridge",
    "example_interfaces", "control_msgs",
}
# Names this project cannot install next to its pins: not ROS 2, not a real error.
EXCLUDED = {
    "mcp": "needs jsonschema>=4.20, which conflicts with the jsonschema==4.10.3 pin",
}
# A script that needs ROS 2 only because of what it does when it runs, not what it
# imports: always ROS, whatever its imports say. Keys are paths relative to SLIDES.
RUNTIME_ROS = {
    "lecture8/code/stop_test.py": "calls ros_node(), which imports rclpy, at module level",
}


def optional_handler(handler) -> bool:
    """True if an except clause catches ImportError or ModuleNotFoundError."""
    names = {"ImportError", "ModuleNotFoundError"}
    t = handler.type
    if isinstance(t, ast.Tuple):
        return any(isinstance(e, ast.Name) and e.id in names for e in t.elts)
    return isinstance(t, ast.Name) and t.id in names


def walk(stmts, optional=False):
    """Yield (top_level_name, optional) for every import under a list of statements,
    not descending into a function, a lambda or a class method."""
    for stmt in stmts:
        if isinstance(stmt, ast.Import):
            for alias in stmt.names:
                yield alias.name.split(".")[0], optional
        elif isinstance(stmt, ast.ImportFrom):
            if stmt.level:   # a relative import: resolved against the script's folder
                if stmt.module:
                    yield stmt.module.split(".")[0], optional
                else:
                    for alias in stmt.names:
                        yield alias.name, optional
            elif stmt.module:
                yield stmt.module.split(".")[0], optional
        elif isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue   # only runs when called, not at import time
        elif isinstance(stmt, ast.ClassDef):
            yield from walk(stmt.body, optional)
        elif isinstance(stmt, ast.Try):
            body_optional = optional or any(optional_handler(h) for h in stmt.handlers)
            yield from walk(stmt.body, body_optional)
            yield from walk(stmt.orelse, optional)
            for h in stmt.handlers:
                yield from walk(h.body, optional)
            yield from walk(stmt.finalbody, optional)
        elif isinstance(stmt, ast.If):
            yield from walk(stmt.body, optional)
            yield from walk(stmt.orelse, optional)
        elif isinstance(stmt, (ast.With, ast.AsyncWith)):
            yield from walk(stmt.body, optional)
        elif isinstance(stmt, (ast.For, ast.AsyncFor, ast.While)):
            yield from walk(stmt.body, optional)
            yield from walk(stmt.orelse, optional)
        elif hasattr(ast, "Match") and isinstance(stmt, ast.Match):
            for case in stmt.cases:
                yield from walk(case.body, optional)
        # anything else (an assignment, an expression, a return) holds no import


def local_file(name: str, script: Path, source: str) -> Path | None:
    """The lecture file or package this name is, if it is one of the lecture's own,
    checked in order: the script's own folder; the lecture's code/ folder (for a
    script under code/tests/); SLIDES/lecture8/code (when the script's text names
    lecture8)."""
    folders = [script.parent]
    if script.parent.name == "tests":
        folders.append(script.parent.parent)
    if "lecture8" in source:
        folders.append(SLIDES / "lecture8" / "code")
    for folder in folders:
        candidate = folder / f"{name}.py"
        if candidate.is_file():
            return candidate
        candidate = folder / name / "__init__.py"
        if candidate.is_file():
            return candidate
    return None


def find_spec_safe(name: str):
    try:
        return importlib.util.find_spec(name)
    except (ImportError, ValueError):
        return None


def missing_names(script: Path, cache: dict) -> set:
    """The names this script needs, other than an optional one, that are missing,
    after resolving its own local names recursively."""
    key = script.resolve()
    if key in cache:
        return cache[key]
    cache[key] = set()   # a placeholder while this file is being read, for a cycle
    try:
        source = script.read_text()
        tree = ast.parse(source, filename=str(script))
    except (SyntaxError, UnicodeDecodeError, OSError):
        cache[key] = {"<unreadable>"}
        return cache[key]
    missing = set()
    for name, optional in walk(tree.body):
        local = local_file(name, script, source)
        if local is not None:
            sub = missing_names(local, cache)
            if sub and not optional:
                missing |= sub
            continue
        if find_spec_safe(name) is None and not optional:
            missing.add(name)
    cache[key] = missing
    return missing


def verdict(missing: set) -> tuple[str, str]:
    if not missing:
        return "managed", "ok"
    ros_missing = {n for n in missing if n in ROS}
    rest = missing - ros_missing
    if not rest:
        return "ROS", ", ".join(sorted(missing))
    if rest <= EXCLUDED.keys():
        return "excluded", "; ".join(f"{n}: {EXCLUDED[n]}" for n in sorted(rest))
    return "error", "missing " + ", ".join(sorted(missing))


lines, manifest = [], {}
counts = {"managed": 0, "ROS": 0, "error": 0, "excluded": 0}
cache: dict = {}
for lecture in sorted(SLIDES.glob("lecture*"), key=lambda p: int(re.sub(r"\D", "", p.name))):
    code = lecture / "code"
    if not code.is_dir():
        continue
    both, slides_only = [], []
    for py in sorted(code.rglob("*.py")):
        if "__pycache__" in py.parts:
            continue
        rel = py.relative_to(lecture).as_posix()
        override = RUNTIME_ROS.get(py.relative_to(SLIDES).as_posix())
        if override is not None:
            kind, detail = "ROS", override
        else:
            kind, detail = verdict(missing_names(py, cache))
        counts[kind] += 1
        lines.append(f"{lecture.name}\t{rel}\t{kind}\t{detail}")
        if kind == "managed":
            (both if (DOCS / lecture.name / rel).is_file() else slides_only).append(rel)
    if not both and not slides_only:
        continue
    for f in sorted(code.rglob("*")):
        if not f.is_file() or f.suffix not in DATA:
            continue
        if "__pycache__" in f.parts or "btcpp" in f.relative_to(code).parts:
            continue
        rel = f.relative_to(lecture).as_posix()
        (both if (DOCS / lecture.name / rel).is_file() else slides_only).append(rel)
    manifest[lecture.name] = {"both": both, "slides": slides_only}

(ROOT / "tools" / "classification.txt").write_text("\n".join(lines) + "\n")
out = ["# Managed files per lecture, written by tools/classify.py; review before the first sync.\n"]
for lecture, entry in manifest.items():
    out.append(f"[{lecture}]")
    for key in ("both", "slides"):
        items = ",\n    ".join(f'"{x}"' for x in entry[key])
        out.append(f"{key} = [\n    {items},\n]" if entry[key] else f"{key} = []")
    out.append("")
(ROOT / "tools" / "manifest.toml").write_text("\n".join(out))
print(f"{counts['managed']} managed, {counts['ROS']} ROS, {counts['error']} error, "
      f"{counts['excluded']} excluded")
