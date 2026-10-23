"""L13 slide listings from outputs/, and the check that each deck listing matches its file.

  build listings_l13.json   write outputs/listings/<name>.txt for each entry
  check DECK.tex DIR        L8's check: every textcodebasic block follows '% listing: <name>'
                            and equals DIR/<name>.txt byte for byte; every pythoncodebasic
                            block after '% excerpt: <path>' is a run of whole lines of that file
  paste DECK.tex DIR        L8's paste: write each marked listing's file into its block

L8's listings.py (lecture8/code) does the same with one line range per listing. An L13
entry is a list of parts, each from its own outputs file (or a fixed "text" line, such as
"..." to mark lines left out): the lines from the first line
that starts with "from" to the next line that starts with "to" (or "lines" lines in all),
with long lines cut, lines that start with a "drop" prefix removed and repeats counted.
So no output is typed onto a slide by hand."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lecture8" / "code"))
from listings import WIDTH, check, drop_repeats, paste, select, shorten   # noqa: E402


def part_lines(outputs, part):
    if "text" in part:   # a fixed line, such as "..." where lines are left out
        return [part["text"]]
    lines = (outputs / part["source"]).read_text().splitlines()
    if "lines" in part:
        i = next(k for k, line in enumerate(lines) if line.startswith(part["from"]))
        return lines[i:i + part["lines"]]
    return select(lines, part.get("from"), part.get("to"))


def build(spec_path):
    spec_path = Path(spec_path)
    outputs = spec_path.resolve().parent.parent / "outputs"
    (outputs / "listings").mkdir(exist_ok=True)
    for e in json.loads(spec_path.read_text())["listings"]:
        lines = [line for part in e["parts"] for line in part_lines(outputs, part)]
        lines = [line for line in lines if not any(line.startswith(p) for p in e.get("drop", []))]
        lines = drop_repeats([shorten(line, e.get("width", WIDTH)) for line in lines])
        (outputs / "listings" / f"{e['name']}.txt").write_text("\n".join(lines) + "\n")


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
