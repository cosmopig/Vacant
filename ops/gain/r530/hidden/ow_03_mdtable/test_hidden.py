"""ow_03_mdtable — hidden checks, 14. **Never enters a workspace.**

Generated from bank/ow_03_mdtable/hidden/*.py by export_bank.py; the
anchor table is in ANCHORS.md beside this file.
"""
import solution


def check_h01_cjk_display_width():
    # anchor_kind: goal
    # anchor: some of the cells contain Chinese and Japanese text
    # derivation: when a column holds wide characters the rows only line up if width is
    # measured in columns rather than in characters.

    import unicodedata


    def _width(text):
        return sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in text)


    def _bank_entry(solution):
        text = "| 品目 | qty |\n| --- | --- |\n| 鉛筆と消しゴム | 3 |\n| pen | 11 |\n"
        got = solution.realign(text)
        widths = [_width(line) for line in got.rstrip("\n").split("\n")]
        assert len(set(widths)) == 1, "args=%r got=%r want=%r" % (text, widths, "one common width")
    _bank_entry(solution)


def check_h02_four_markers():
    # anchor_kind: contract
    # anchor: A separator cell keeps the alignment markers it had
    # derivation: all four markers appear in one table and all four have to survive,
    # each stretched to its own column width.


    def _bank_entry(solution):
        text = "| plain | left | right | centre |\n| --- | :--- | ---: | :---: |\n| aaaaaa | b | c | d |\n"
        got = solution.realign(text)
        sep = got.split("\n")[1]
        cells = [c.strip() for c in sep.strip().strip("|").split("|")]
        shapes = [(c.startswith(":"), c.endswith(":") and len(c) >= 2) for c in cells]
        want = [(False, False), (True, False), (False, True), (True, True)]
        assert shapes == want, "args=%r got=%r want=%r" % (text, shapes, want)
        assert all("-" in c for c in cells), "args=%r got=%r want=%r" % (text, cells, "each keeps dashes")
    _bank_entry(solution)


def check_h03_escaped_pipe():
    # anchor_kind: goal
    # anchor: some are escaped
    # derivation: a backslash-escaped pipe is content, so the row still has two cells
    # and the escape sequence survives into the output.


    def _separators(line):
        return sum(1 for i, ch in enumerate(line)
                   if ch == "|" and (i == 0 or line[i - 1] != "\\"))


    def _bank_entry(solution):
        text = "| key | value |\n| --- | --- |\n| or | a \\| b |\n"
        got = solution.realign(text)
        body = got.split("\n")[2]
        assert "a \\| b" in body, "args=%r got=%r want=%r" % (text, body, "a \\| b kept as one cell")
        got_n = _separators(body)
        assert got_n == 3, "args=%r got=%r want=%r" % (text, got_n, 3)
    _bank_entry(solution)


def check_h04_pipe_in_inline_code():
    # anchor_kind: goal
    # anchor: some sit inside inline code
    # derivation: a pipe between backticks belongs to the code span, so the row keeps
    # two cells and the backticks stay where they were.


    def _bank_entry(solution):
        text = "| what | how |\n| --- | --- |\n| alternation | `a|b` |\n"
        got = solution.realign(text)
        body = got.split("\n")[2]
        assert "`a|b`" in body, "args=%r got=%r want=%r" % (text, body, "`a|b` kept intact")
        assert body.count("|") == 4, "args=%r got=%r want=%r" % (text, body.count("|"), 4)
    _bank_entry(solution)


def check_h05_backtick_fence_untouched():
    # anchor_kind: goal
    # anchor: some are inside fenced code blocks that happen to show a table
    # derivation: a table drawn inside a backtick fence is sample text, not structure,
    # so those lines come back byte for byte.


    def _bank_entry(solution):
        text = "intro\n\n```\n|a|b|\n|---|---|\n|1|2|\n```\n\nend\n"
        got = solution.realign(text)
        assert got == text, "args=%r got=%r want=%r" % (text, got, text)
    _bank_entry(solution)


def check_h06_tilde_fence_untouched():
    # anchor_kind: contract
    # anchor: every line inside a fenced code block opened by three backticks or three
    # tildes
    # derivation: the tilde fence is the other spelling of the same thing and must be
    # honoured identically.


    def _bank_entry(solution):
        text = "~~~\n|x|y|\n|--|--|\n|9|8|\n~~~\n"
        got = solution.realign(text)
        assert got == text, "args=%r got=%r want=%r" % (text, got, text)
    _bank_entry(solution)


def check_h07_missing_edge_pipes():
    # anchor_kind: goal
    # anchor: some rows are missing the pipes at the start and end
    # derivation: a table written without edge pipes is still a table, and the output
    # gets the edge pipes the contract requires.


    def _bank_entry(solution):
        text = "a | b\n--- | ---\n1 | 2\n"
        got = solution.realign(text)
        for line in got.rstrip("\n").split("\n"):
            assert line.startswith("| ") and line.endswith(" |"), (
                "args=%r got=%r want=%r" % (text, line, "| ... |"))
        assert "1" in got and "2" in got, "args=%r got=%r want=%r" % (text, got, "cells preserved")
    _bank_entry(solution)


def check_h08_ragged_rows():
    # anchor_kind: goal
    # anchor: some rows have more cells than the header
    # derivation: the table grows to the widest row and the short rows are filled with
    # empty cells, so every output row has the same number of separators.


    def _bank_entry(solution):
        text = "| a | b |\n| --- | --- |\n| 1 | 2 | 3 |\n| 4 |\n"
        got = solution.realign(text)
        lines = got.rstrip("\n").split("\n")
        counts = [line.count("|") for line in lines]
        assert counts == [4, 4, 4, 4], "args=%r got=%r want=%r" % (text, counts, [4, 4, 4, 4])
        assert "3" in lines[2], "args=%r got=%r want=%r" % (text, lines[2], "the third cell survives")
    _bank_entry(solution)


def check_h09_empty_cells():
    # anchor_kind: goal
    # anchor: some cells are empty
    # derivation: an empty cell is still a column, padded to the column width and never
    # collapsed away.

    import unicodedata


    def _width(text):
        return sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in text)


    def _bank_entry(solution):
        text = "| p | q |\n| --- | --- |\n| |longish|\n"
        got = solution.realign(text)
        lines = got.rstrip("\n").split("\n")
        assert all(line.count("|") == 3 for line in lines), (
            "args=%r got=%r want=%r" % (text, [l.count("|") for l in lines], [3, 3, 3]))
        widths = [_width(line) for line in lines]
        assert len(set(widths)) == 1, "args=%r got=%r want=%r" % (text, widths, "one common width")
    _bank_entry(solution)


def check_h10_idempotent():
    # anchor_kind: goal
    # anchor: running it twice must produce the same file as running it once
    # derivation: the pre-commit hook would loop forever otherwise, so the second pass
    # has to be a no-op on the first pass's output.


    def _bank_entry(solution):
        text = "| 名稱 |n|\n|:--|--:|\n|甲|1|\n|lengthy name|22|\n\nnot a table\n"
        once = solution.realign(text)
        twice = solution.realign(once)
        assert once == twice, "args=%r got=%r want=%r" % (text, twice, once)
    _bank_entry(solution)


def check_h11_crlf_preserved():
    # anchor_kind: goal
    # anchor: files saved on Windows must come back with the line endings they arrived
    # with
    # derivation: a CRLF document must still be CRLF afterwards, and must not have
    # gained a lone LF anywhere.


    def _bank_entry(solution):
        text = "| a | bb |\r\n| --- | --- |\r\n| 1 | 2 |\r\n"
        got = solution.realign(text)
        assert got.count("\r\n") == 3, "args=%r got=%r want=%r" % (text, got.count("\r\n"), 3)
        assert got.count("\n") == got.count("\r\n"), (
            "args=%r got=%r want=%r" % (text, got, "no bare LF"))
    _bank_entry(solution)


def check_h12_no_table_at_all():
    # anchor_kind: goal
    # anchor: A document with no table in it at all must come back byte for byte.
    # derivation: prose that happens to contain a pipe is not a table, because no
    # separator row follows it.


    def _bank_entry(solution):
        text = "Run `grep x | wc -l` and read the count.\nNothing here is a table.\n"
        got = solution.realign(text)
        assert got == text, "args=%r got=%r want=%r" % (text, got, text)
    _bank_entry(solution)


def check_h13_table_touching_prose():
    # anchor_kind: goal
    # anchor: leaves everything that is not a table exactly as it was
    # derivation: with no blank line above or below, the neighbouring prose lines must
    # be returned untouched while the table between them is rewritten.


    def _bank_entry(solution):
        text = "Costs below:\n|item|cost|\n|---|---|\n|tea|4|\nThat is all.\n"
        got = solution.realign(text)
        lines = got.split("\n")
        assert lines[0] == "Costs below:", "args=%r got=%r want=%r" % (text, lines[0], "Costs below:")
        assert lines[4] == "That is all.", "args=%r got=%r want=%r" % (text, lines[4], "That is all.")
        assert lines[1].startswith("| item"), "args=%r got=%r want=%r" % (text, lines[1], "| item ... |")
    _bank_entry(solution)


def check_h14_final_newline():
    # anchor_kind: contract
    # anchor: the presence or absence of a final newline is unchanged
    # derivation: a document whose last line has no newline must not gain one, and one
    # that has a newline must not lose it.


    def _bank_entry(solution):
        without = "|a|b|\n|---|---|\n|1|2|"
        got = solution.realign(without)
        assert not got.endswith("\n"), "args=%r got=%r want=%r" % (without, got[-3:], "no trailing newline")

        with_nl = without + "\n"
        got = solution.realign(with_nl)
        assert got.endswith("\n") and not got.endswith("\n\n"), (
            "args=%r got=%r want=%r" % (with_nl, got[-3:], "exactly one trailing newline"))
    _bank_entry(solution)
