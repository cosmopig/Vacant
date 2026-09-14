"""Checks that ship with this task. You can run them yourself: `sh run_tests.sh`.

Each `check_*` function is one check. A check passes when it returns
normally. These are the same checks the client runs before accepting
the work.
"""
import solution


def check_v01_wraps_to_width():
    """Visible check 1: a paragraph comes back with no line over the width."""

    import unicodedata


    def _width(text):
        return sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in text)


    def _bank_entry(solution):
        text = ("the quick brown fox jumps over the lazy dog and then goes back "
                "to sleep under the table\n")
        got = solution.reflow(text, 20)
        lines = got.rstrip("\n").split("\n")
        for line in lines:
            assert _width(line) <= 20, "args=%r got=%r want=%r" % (20, line, "<= 20 columns")
        assert " ".join(got.split()) == " ".join(text.split()), (
            "args=%r got=%r want=%r" % (text, " ".join(got.split()), " ".join(text.split())))
    _bank_entry(solution)


def check_v02_bullet_hanging_indent():
    """Visible check 2: a bullet's continuation lines sit under the text."""


    def _bank_entry(solution):
        text = "- alpha beta gamma delta epsilon zeta eta theta\n"
        got = solution.reflow(text, 18)
        lines = got.rstrip("\n").split("\n")
        assert len(lines) > 1, "args=%r got=%r want=%r" % (text, lines, "more than one line")
        assert lines[0].startswith("- "), "args=%r got=%r want=%r" % (text, lines[0], "- ...")
        for line in lines[1:]:
            assert line.startswith("  ") and not line.startswith("- "), (
                "args=%r got=%r want=%r" % (text, line, "two spaces of hanging indent"))
    _bank_entry(solution)


def check_v03_fence_and_bad_width():
    """Visible check 3: fenced code is left alone; a nonsense width is refused."""


    def _bank_entry(solution):
        text = "note\n\n```\nthis fenced line is far longer than the width given here\n```\n"
        got = solution.reflow(text, 12)
        assert "this fenced line is far longer than the width given here" in got, (
            "args=%r got=%r want=%r" % (text, got, "the fenced line unchanged"))

        for width in (0, -5):
            try:
                solution.reflow("hello", width)
            except ValueError:
                continue
            raise AssertionError("args=%r got=%r want=%r" % (width, "wrapped", "ValueError"))
    _bank_entry(solution)
