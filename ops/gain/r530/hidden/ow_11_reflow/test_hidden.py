"""ow_11_reflow — hidden checks, 14. **Never enters a workspace.**

Generated from bank/ow_11_reflow/hidden/*.py by export_bank.py; the
anchor table is in ANCHORS.md beside this file.
"""
import solution


def check_h01_wide_characters_count_two():
    # anchor_kind: goal
    # anchor: Chinese takes two columns per character in their terminal
    # derivation: a line of Chinese is only within the width when each character is
    # counted as two columns.

    import unicodedata


    def _width(text):
        return sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in text)


    def _bank_entry(solution):
        text = "這是一段中文筆記用來測試換行寬度是否以顯示寬度計算\n"
        got = solution.reflow(text, 10)
        for line in got.rstrip("\n").split("\n"):
            assert _width(line) <= 10, "args=%r got=%r want=%r" % (10, line, "<= 10 columns")
        assert "".join(got.split()) == "".join(text.split()), (
            "args=%r got=%r want=%r" % (text, "".join(got.split()), "".join(text.split())))
    _bank_entry(solution)


def check_h02_break_between_wide_characters():
    # anchor_kind: goal
    # anchor: it can be broken between any two characters without a space appearing at
    # the break
    # derivation: a Chinese run with no spaces in it still wraps, and putting the lines
    # back together with nothing between them gives the original text.


    def _bank_entry(solution):
        text = "甲乙丙丁戊己庚辛壬癸子丑寅卯辰巳午未申酉戌亥"
        got = solution.reflow(text, 8)
        lines = got.split("\n")
        assert len(lines) >= 5, "args=%r got=%r want=%r" % (8, len(lines), ">= 5 lines")
        assert "".join(lines) == text, "args=%r got=%r want=%r" % (text, "".join(lines), text)
        for line in lines:
            assert " " not in line, "args=%r got=%r want=%r" % (text, line, "no spaces introduced")
    _bank_entry(solution)


def check_h03_paragraph_indent_carried_down():
    # anchor_kind: goal
    # anchor: Their notes have indented blocks
    # derivation: a paragraph that started indented keeps that indentation on every one
    # of its lines.


    def _bank_entry(solution):
        text = "    one two three four five six seven eight nine ten eleven twelve\n"
        got = solution.reflow(text, 24)
        lines = got.rstrip("\n").split("\n")
        assert len(lines) > 1, "args=%r got=%r want=%r" % (24, lines, "more than one line")
        for line in lines:
            assert line.startswith("    ") and line[4] != " ", (
                "args=%r got=%r want=%r" % (text, line, "four spaces of indent"))
    _bank_entry(solution)


def check_h04_numbered_bullets():
    # anchor_kind: contract
    # anchor: or digits followed by `. `
    # derivation: a numbered item hangs under its text, so the continuation indent is
    # as wide as the number, the dot and the space together.


    def _bank_entry(solution):
        text = "10. alpha beta gamma delta epsilon zeta eta theta iota\n"
        got = solution.reflow(text, 20)
        lines = got.rstrip("\n").split("\n")
        assert lines[0].startswith("10. "), "args=%r got=%r want=%r" % (text, lines[0], "10. ...")
        for line in lines[1:]:
            assert line.startswith("    ") and line[4] != " ", (
                "args=%r got=%r want=%r" % (text, line, "four spaces of hanging indent"))
    _bank_entry(solution)


def check_h05_star_bullets_and_nesting_indent():
    # anchor_kind: contract
    # anchor: a bullet marker -- `- `, `* `, or digits followed by `. `
    # derivation: the star spelling behaves like the dash, and an indented bullet hangs
    # under its own text rather than under the left margin.


    def _bank_entry(solution):
        text = "  * alpha beta gamma delta epsilon zeta eta theta iota kappa\n"
        got = solution.reflow(text, 20)
        lines = got.rstrip("\n").split("\n")
        assert lines[0].startswith("  * "), "args=%r got=%r want=%r" % (text, lines[0], "  * ...")
        for line in lines[1:]:
            assert line.startswith("    ") and line[4] != " ", (
                "args=%r got=%r want=%r" % (text, line, "four spaces of hanging indent"))
    _bank_entry(solution)


def check_h06_each_bullet_is_its_own():
    # anchor_kind: goal
    # anchor: Each bullet in a list is its own thought and must not be glued onto the
    # one above it.
    # derivation: three short bullets on three lines come back as three bullets, not as
    # one filled paragraph.


    def _bank_entry(solution):
        text = "- one\n- two\n- three\n"
        got = solution.reflow(text, 60)
        lines = got.rstrip("\n").split("\n")
        assert lines == ["- one", "- two", "- three"], (
            "args=%r got=%r want=%r" % (text, lines, ["- one", "- two", "- three"]))
    _bank_entry(solution)


def check_h07_blank_runs_kept():
    # anchor_kind: goal
    # anchor: however many there were is however many they want back
    # derivation: a run of three blank lines stays three blank lines, and the
    # paragraphs around it are still wrapped.


    def _bank_entry(solution):
        text = "first para\n\n\n\nsecond para\n"
        got = solution.reflow(text, 40)
        lines = got.rstrip("\n").split("\n")
        assert lines == ["first para", "", "", "", "second para"], (
            "args=%r got=%r want=%r" % (text, lines,
                                        ["first para", "", "", "", "second para"]))
    _bank_entry(solution)


def check_h08_fence_contents_untouched():
    # anchor_kind: goal
    # anchor: code fenced off with backticks that must not be touched
    # derivation: every line between the fences comes back byte for byte, including
    # leading spaces, long lines and lines that look like bullets.


    def _bank_entry(solution):
        inner = ["    indented   spacing   kept", "- looks like a bullet but is code",
                 "a" * 80]
        text = "intro\n\n```\n" + "\n".join(inner) + "\n```\n\nafter\n"
        got = solution.reflow(text, 15)
        for line in inner:
            assert "\n" + line + "\n" in got, (
                "args=%r got=%r want=%r" % (15, line, "the fenced line unchanged"))
    _bank_entry(solution)


def check_h09_long_piece_sticks_out():
    # anchor_kind: goal
    # anchor: they would rather it stick out than be chopped in half
    # derivation: a single long run with no spaces occupies a line of its own, whole,
    # and the words around it are still wrapped normally.


    def _bank_entry(solution):
        long_one = "https://example.com/a/very/long/path/that/never/ends/at/all"
        text = "see %s now\n" % long_one
        got = solution.reflow(text, 20)
        lines = got.rstrip("\n").split("\n")
        assert long_one in lines, "args=%r got=%r want=%r" % (text, lines, "the long run on its own line")
    _bank_entry(solution)


def check_h10_bad_width_refused():
    # anchor_kind: goal
    # anchor: A width that makes no sense should be refused.
    # derivation: zero and negative widths raise rather than looping or returning
    # something arbitrary.


    def _bank_entry(solution):
        for width in (0, -1, -100):
            try:
                solution.reflow("some words here", width)
            except ValueError:
                continue
            raise AssertionError("args=%r got=%r want=%r" % (width, "wrapped", "ValueError"))
    _bank_entry(solution)


def check_h11_whitespace_collapses():
    # anchor_kind: contract
    # anchor: runs of spaces and tabs separate words and are replaced by a single space
    # derivation: doubled spaces and tabs between words become one space each, and no
    # output line is left with trailing whitespace.


    def _bank_entry(solution):
        text = "alpha    beta\tgamma \t delta\n"
        got = solution.reflow(text, 40)
        assert got == "alpha beta gamma delta\n", (
            "args=%r got=%r want=%r" % (text, got, "alpha beta gamma delta\n"))
        for line in got.split("\n"):
            assert line == line.rstrip(), "args=%r got=%r want=%r" % (text, line, "no trailing space")
    _bank_entry(solution)


def check_h12_final_newline():
    # anchor_kind: contract
    # anchor: The presence or absence of a final newline is unchanged.
    # derivation: a note without a final newline must not gain one, and one with a
    # final newline must keep exactly one.


    def _bank_entry(solution):
        without = "alpha beta gamma delta"
        got = solution.reflow(without, 10)
        assert not got.endswith("\n"), "args=%r got=%r want=%r" % (without, got[-3:], "no final newline")

        got = solution.reflow(without + "\n", 10)
        assert got.endswith("\n") and not got.endswith("\n\n"), (
            "args=%r got=%r want=%r" % (without + "\n", got[-3:], "exactly one final newline"))
    _bank_entry(solution)


def check_h13_mixed_scripts_in_one_word():
    # anchor_kind: contract
    # anchor: A break may fall between any two characters when at least one of them is
    # wide, and no space is inserted at such a break.
    # derivation: a run that mixes Latin letters and Chinese may break where the two
    # meet, and the Latin part is not broken inside itself.


    def _bank_entry(solution):
        text = "版本abcdefgh版本"
        got = solution.reflow(text, 6)
        lines = got.split("\n")
        assert "".join(lines) == text, "args=%r got=%r want=%r" % (text, "".join(lines), text)
        assert any("abcdefgh" in line for line in lines), (
            "args=%r got=%r want=%r" % (text, lines, "abcdefgh kept whole"))
    _bank_entry(solution)


def check_h14_bullet_after_paragraph():
    # anchor_kind: goal
    # anchor: bullet lists whose continuation lines should line up under the text and
    # not under the bullet
    # derivation: a bullet that follows a plain paragraph with no blank line between
    # them starts its own paragraph and hangs its own continuation.


    def _bank_entry(solution):
        text = "intro words here\n- item one two three four five six seven eight\n"
        got = solution.reflow(text, 20)
        lines = got.rstrip("\n").split("\n")
        assert lines[0] == "intro words here", (
            "args=%r got=%r want=%r" % (text, lines[0], "intro words here"))
        assert lines[1].startswith("- item"), "args=%r got=%r want=%r" % (text, lines[1], "- item ...")
        for line in lines[2:]:
            assert line.startswith("  ") and line[2] != " ", (
                "args=%r got=%r want=%r" % (text, line, "two spaces of hanging indent"))
    _bank_entry(solution)
