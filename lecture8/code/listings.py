"""Slide listings from outputs/, and a check that each deck listing matches its file.

  build SPEC.json         write outputs/listings/<name>.txt for each entry: the lines
                          between two prefixes, long lines cut, repeats dropped
  check DECK.tex DIR      every textcodebasic block must follow '% listing: <name>' and
                          equal DIR/<name>.txt byte for byte; every pythoncodebasic block
                          after '% excerpt: <path>' must be a run of whole lines of that file
  paste DECK.tex DIR      write each marked listing's file into its block

So no output is typed onto a slide by hand."""
import json
import re
import sys
from pathlib import Path

WIDTH = 92   # characters per line, chosen: checked on the rendered pages (textcodebasic, \small)
BEGIN = re.compile(r"\\begin\{(textcodebasic|pythoncodebasic)\}")
MARK = re.compile(r"% (listing|excerpt): (\S+)$")


def shorten(line, width=WIDTH):
    return line if len(line) <= width else line[: width - 4] + " ..."


def drop_repeats(lines):
    out, i = [], 0
    while i < len(lines):
        j = i
        while j + 1 < len(lines) and lines[j + 1] == lines[i]:
            j += 1
        out.append(lines[i])
        if j > i:
            out.append(f"  ({j - i} more times)")
        i = j + 1
    return out


def select(lines, start=None, stop=None):
    if start is None:
        return list(lines)
    i = next(k for k, line in enumerate(lines) if line.startswith(start))
    if stop is None:
        return lines[i:]
    j = next(k for k in range(i + 1, len(lines)) if lines[k].startswith(stop))
    return lines[i:j + 1]


def build(spec_path):
    spec_path = Path(spec_path)
    outputs = spec_path.resolve().parent.parent / "outputs"
    (outputs / "listings").mkdir(exist_ok=True)
    for e in json.loads(spec_path.read_text())["listings"]:
        lines = select((outputs / e["source"]).read_text().splitlines(), e.get("from"), e.get("to"))
        lines = [line for line in lines if not any(line.startswith(p) for p in e.get("drop", []))]
        lines = drop_repeats([shorten(line, e.get("width", WIDTH)) for line in lines])
        (outputs / "listings" / f"{e['name']}.txt").write_text("\n".join(lines) + "\n")


def _blocks(lines):
    i = 0
    while i < len(lines):
        m = BEGIN.match(lines[i].strip())
        if m:
            kind = m.group(1)
            mark = MARK.match(lines[i - 1].strip()) if i else None
            end = next(k for k in range(i + 1, len(lines)) if lines[k].strip() == f"\\end{{{kind}}}")
            yield i, kind, (mark.groups() if mark else None), end
            i = end
        i += 1


def _raw(path):
    """A file's exact text. newline="" disables universal-newline translation on
    read, so CRLF and a bare CR survive instead of collapsing to LF; Path.read_text()
    would translate both away and hide a real difference from the check below."""
    with open(path, newline="") as f:
        return f.read()


def check(tex, listings_dir):
    tex, listings_dir = Path(tex), Path(listings_dir)
    raw_text = _raw(tex)
    lines = raw_text.splitlines()
    raw_lines = raw_text.splitlines(keepends=True)
    problems = []
    for start, kind, mark, end in _blocks(lines):
        body = lines[start + 1:end]
        where = f"{tex.name}:{start + 1}"
        if kind == "textcodebasic":
            if not mark or mark[0] != "listing":
                problems.append(f"{where}: textcodebasic without '% listing: <name>'")
                continue
            f = listings_dir / f"{mark[1]}.txt"
            if not f.exists():
                problems.append(f"{where}: no file {f.name}")
            elif "".join(raw_lines[start + 1:end]) != _raw(f):
                problems.append(f"{where}: listing {mark[1]} differs from {f.name}")
        elif mark and mark[0] == "excerpt":
            src = (tex.parent / mark[1]).read_text().splitlines()
            if not any(src[s:s + len(body)] == body for s in range(len(src) - len(body) + 1)):
                problems.append(f"{where}: excerpt is not a run of lines of {mark[1]}")
    return problems


def paste(tex, listings_dir):
    tex = Path(tex)
    raw_text = _raw(tex)
    lines = raw_text.splitlines()
    raw_lines = raw_text.splitlines(keepends=True)
    for start, kind, mark, end in reversed(list(_blocks(lines))):
        if kind == "textcodebasic" and mark and mark[0] == "listing":
            raw_lines[start + 1:end] = [_raw(Path(listings_dir) / f"{mark[1]}.txt")]
    tex.write_text("".join(raw_lines), newline="")


if __name__ == "__main__":
    cmd, *rest = sys.argv[1:]
    if cmd == "build":
        build(rest[0])
    elif cmd == "paste":
        paste(*rest)
    elif cmd == "check":
        found = check(*rest)
        print("\n".join(found) or f"{rest[0]}: every listing matches")
        sys.exit(1 if found else 0)
