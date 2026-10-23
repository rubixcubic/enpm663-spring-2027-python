"""listings.py: the filter, and the byte-for-byte check of every deck listing."""
from listings import check, drop_repeats, paste, select, shorten

BLOCK = "% listing: x\n\\begin{textcodebasic}[][]\nBODY\\end{textcodebasic}\n"   # replace, not format: LaTeX braces


def test_shorten():
    assert shorten("x" * 10, 8) == "xxxx ..."
    assert shorten("short", 8) == "short"


def test_drop_repeats():
    assert drop_repeats(["a", "b", "b", "b", "c"]) == ["a", "b", "  (2 more times)", "c"]


def test_select():
    lines = ["h", "=== Run 1", "a", "call 2: x", "b"]
    assert select(lines, "=== Run 1", "call 2:") == ["=== Run 1", "a", "call 2: x"]
    assert select(lines, "call 2:") == ["call 2: x", "b"]
    assert select(lines) == lines


def test_check_and_paste(tmp_path):
    (tmp_path / "l").mkdir()
    (tmp_path / "l" / "x.txt").write_text("one\ntwo\n")
    tex = tmp_path / "d.tex"
    tex.write_text(BLOCK.replace("BODY", "one\nTWO\n"))
    assert check(tex, tmp_path / "l") == ["d.tex:2: listing x differs from x.txt"]
    paste(tex, tmp_path / "l")
    assert check(tex, tmp_path / "l") == []
    assert tex.read_text() == BLOCK.replace("BODY", "one\ntwo\n")


def test_unmarked_listing_is_reported(tmp_path):
    tex = tmp_path / "d.tex"
    tex.write_text("\\begin{textcodebasic}[][]\nx\n\\end{textcodebasic}\n")
    assert check(tex, tmp_path) == ["d.tex:1: textcodebasic without '% listing: <name>'"]


def test_excerpt_must_be_a_run_of_lines(tmp_path):
    (tmp_path / "code").mkdir()
    (tmp_path / "code" / "f.py").write_text("a = 1\nb = 2\nc = 3\n")
    tex = tmp_path / "d.tex"
    tex.write_text("% excerpt: code/f.py\n\\begin{pythoncodebasic}[][]\nb = 2\nc = 3\n\\end{pythoncodebasic}\n")
    assert check(tex, tmp_path) == []
    tex.write_text("% excerpt: code/f.py\n\\begin{pythoncodebasic}[][]\nb = 2\nc = 4\n\\end{pythoncodebasic}\n")
    assert check(tex, tmp_path) == ["d.tex:2: excerpt is not a run of lines of code/f.py"]


def test_check_detects_crlf_difference(tmp_path):
    # Same text as the listing, but the deck's copy uses CRLF line endings: not
    # byte for byte, so it must fail even though Path.read_text() would hide this.
    (tmp_path / "l").mkdir()
    (tmp_path / "l" / "x.txt").write_bytes(b"one\ntwo\n")
    tex = tmp_path / "d.tex"
    tex.write_bytes(BLOCK.replace("BODY", "one\r\ntwo\r\n").encode())
    assert check(tex, tmp_path / "l") == ["d.tex:2: listing x differs from x.txt"]


def test_check_detects_bare_cr_difference(tmp_path):
    # A bare CR stands in for the newline between "one" and "two": universal-newline
    # translation would turn it into "\n" and hide the difference from the listing.
    (tmp_path / "l").mkdir()
    (tmp_path / "l" / "x.txt").write_bytes(b"one\ntwo\n")
    tex = tmp_path / "d.tex"
    tex.write_bytes(BLOCK.replace("BODY", "one\rtwo\n").encode())
    assert check(tex, tmp_path / "l") == ["d.tex:2: listing x differs from x.txt"]
