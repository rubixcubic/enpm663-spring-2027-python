"""Copy the lecture scripts from this repository into the slides and docs repos, or check the copies.

    uv run python tools/sync_course.py --check    # exit 1 if a copy differs or is missing
    uv run python tools/sync_course.py --write    # copy this repository's files over the copies

tools/manifest.toml lists the managed files per lecture: "both" go to the slides and the docs
repos, "slides" to the slides repo only. tools/course_paths.toml gives the two lecture folders,
relative to this repository. The script never deletes a file and never writes a file the
manifest does not list. Each entry must be a file under a lecture's code/ or outputs/ folder,
with no "..", and the script refuses a destination that is a symlink or that resolves outside
its lecture's folder.
"""
import argparse
import filecmp
import re
import shutil
import sys
import tomllib
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
# Cache folders the "not managed" notes skip: Python and pytest write them, not a person.
SKIP = {"__pycache__", ".pytest_cache"}


def load(root: Path) -> tuple[dict, dict]:
    paths = tomllib.loads((root / "tools" / "course_paths.toml").read_text())
    manifest = tomllib.loads((root / "tools" / "manifest.toml").read_text())
    for name in ("slides", "docs"):
        target = (root / paths[name]).resolve()
        if not target.is_dir():
            sys.exit(f"{name} lecture folder not found: {target}")
        paths[name] = target
    return paths, manifest


def check_entry(lecture: str, rel: str) -> None:
    """Stop unless the entry is a lecture's file under code/ or outputs/, with no ".."."""
    parts = PurePosixPath(rel).parts
    if not re.fullmatch(r"lecture\d+", lecture) or not parts \
            or parts[0] not in ("code", "outputs") or ".." in parts:
        sys.exit(f"manifest entry outside a lecture's code/ and outputs/: {lecture}/{rel}")


def check_destination(dst: Path, folder: Path) -> None:
    """Stop if the copy would be a symlink or would land outside the lecture's folder."""
    if dst.is_symlink():
        sys.exit(f"destination is a symlink, refused: {dst}")
    if not dst.resolve().is_relative_to(folder):
        sys.exit(f"destination resolves outside {folder}, refused: {dst}")


def pairs(root: Path) -> list[tuple[Path, Path]]:
    paths, manifest = load(root)
    out = []
    for lecture, entry in manifest.items():
        for where in ("both", "slides"):
            for rel in entry.get(where, []):
                check_entry(lecture, rel)
                targets = ("slides", "docs") if where == "both" else ("slides",)
                for name in targets:
                    dst = paths[name] / lecture / rel
                    check_destination(dst, paths[name] / lecture)
                    out.append((root / lecture / rel, dst))
    for src, _ in out:
        if not src.is_file():
            sys.exit(f"manifest lists a file this repository does not have: {src.relative_to(root)}")
    return out


def check(root: Path) -> tuple[list[str], list[str]]:
    paths, manifest = load(root)
    problems = []
    managed = set()
    for src, dst in pairs(root):
        managed.add(dst)
        where = "slides" if dst.is_relative_to(paths["slides"]) else "docs"
        rel = dst.relative_to(paths[where])
        if not dst.is_file():
            problems.append(f"{where}: missing {rel}")
        elif not filecmp.cmp(src, dst, shallow=False):
            problems.append(f"{where}: differs {rel}")
    notes = []
    for where in ("slides", "docs"):
        for lecture in manifest:
            folder = paths[where] / lecture
            for sub in ("code", "outputs"):
                for f in sorted((folder / sub).rglob("*")) if (folder / sub).is_dir() else []:
                    if f.is_file() and f not in managed and not SKIP.intersection(f.parts) \
                            and "raw" not in f.relative_to(folder).parts:
                        notes.append(f"{where}: not managed {f.relative_to(paths[where])}")
    return problems, notes


def write(root: Path) -> list[str]:
    todo = pairs(root)
    written = []
    for src, dst in todo:
        if dst.is_file() and filecmp.cmp(src, dst, shallow=False):
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        written.append(str(dst))
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--write", action="store_true")
    args = parser.parse_args()
    if args.write:
        for path in write(ROOT):
            print(f"wrote {path}")
    problems, notes = check(ROOT)
    for line in notes:
        print(line)
    for line in problems:
        print(line)
    print(f"{len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
