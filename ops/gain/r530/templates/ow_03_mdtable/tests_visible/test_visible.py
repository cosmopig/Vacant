"""Checks that ship with this task. You can run them yourself: `sh run_tests.sh`.

Each `check_*` function is one check. A check passes when it returns
normally. These are the same checks the client runs before accepting
the work.
"""
import solution


def check_v01_columns_line_up():
    """Visible check 1: ragged columns come back aligned, including wide characters."""

    import unicodedata


    def _width(text):
        return sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in text)


    def _bank_entry(solution):
        text = "|name|city|\n|---|---|\n|Bo|台北|\n|Alexandra|Oslo|\n"
        got = solution.realign(text)
        lines = got.split("\n")[:4]
        widths = [_width(line) for line in lines]
        assert len(set(widths)) == 1, "args=%r got=%r want=%r" % (text, widths, "all rows the same width")
        for line in lines:
            assert line.startswith("| ") and line.endswith(" |"), (
                "args=%r got=%r want=%r" % (text, line, "| ... |"))
        assert "Alexandra" in got and "台北" in got, (
            "args=%r got=%r want=%r" % (text, got, "cell text preserved"))
    _bank_entry(solution)


def check_v02_non_table_untouched():
    """Visible check 2: prose is not a table, and a document without one is returned as-is."""


    def _bank_entry(solution):
        text = "# Heading\n\nJust a paragraph about nothing.\n\n- a bullet\n"
        got = solution.realign(text)
        assert got == text, "args=%r got=%r want=%r" % (text, got, text)

        mixed = "before\n|h|\n|---|\n|v|\nafter\n"
        got = solution.realign(mixed)
        lines = got.split("\n")
        assert lines[0] == "before", "args=%r got=%r want=%r" % (mixed, lines[0], "before")
        assert lines[4] == "after", "args=%r got=%r want=%r" % (mixed, lines[4], "after")
    _bank_entry(solution)


def check_v03_alignment_markers():
    """Visible check 3: the separator row keeps the alignment it was given."""


    def _bank_entry(solution):
        text = "| l | c | r |\n|:--|:-:|--:|\n| 1 | 2 | 3 |\n"
        got = solution.realign(text)
        sep = got.split("\n")[1]
        cells = [c.strip() for c in sep.strip().strip("|").split("|")]
        assert cells[0].startswith(":") and not cells[0].endswith(":"), (
            "args=%r got=%r want=%r" % (text, cells[0], "left marker kept"))
        assert cells[1].startswith(":") and cells[1].endswith(":"), (
            "args=%r got=%r want=%r" % (text, cells[1], "centre marker kept"))
        assert cells[2].endswith(":") and not cells[2].startswith(":"), (
            "args=%r got=%r want=%r" % (text, cells[2], "right marker kept"))
    _bank_entry(solution)
