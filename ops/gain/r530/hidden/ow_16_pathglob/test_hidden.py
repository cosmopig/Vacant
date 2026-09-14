"""ow_16_pathglob — hidden checks, 13. **Never enters a workspace.**

Generated from bank/ow_16_pathglob/hidden/*.py by export_bank.py; the
anchor table is in ANCHORS.md beside this file.
"""
import solution


def check_h01_star_does_not_cross_a_slash():
    # anchor_kind: goal
    # anchor: A star should stay inside one directory level
    # derivation: a star in the middle of a pattern cannot swallow a slash, so a deeper
    # path does not match a shallower pattern.


    def _bank_entry(solution):
        cases = [("a/*/c", "a/b/c", True), ("a/*/c", "a/b/x/c", False),
                 ("*", "one", True), ("*", "one/two", False),
                 ("a*z", "abcz", True), ("a*z", "ab/cz", False)]
        for pattern, path, want in cases:
            got = solution.matches(pattern, path)
            assert got is want, "args=%r got=%r want=%r" % ((pattern, path), got, want)
    _bank_entry(solution)


def check_h02_question_mark_is_one_character():
    # anchor_kind: goal
    # anchor: They also need a single-character wildcard
    # derivation: exactly one character, no more and no fewer, and never the separator.


    def _bank_entry(solution):
        cases = [("a?c", "abc", True), ("a?c", "ac", False), ("a?c", "abbc", False),
                 ("a?c", "a/c", False)]
        for pattern, path, want in cases:
            got = solution.matches(pattern, path)
            assert got is want, "args=%r got=%r want=%r" % ((pattern, path), got, want)
    _bank_entry(solution)


def check_h03_double_star_may_swallow_nothing():
    # anchor_kind: goal
    # anchor: that has to work even when there is nothing underneath at all
    # derivation: the double star standing for zero segments is the case an
    # at-least-one implementation gets wrong.


    def _bank_entry(solution):
        cases = [("src/**/main.py", "src/main.py", True),
                 ("**/main.py", "main.py", True),
                 ("a/**/b/**/c", "a/b/c", True),
                 ("**", "anything", True)]
        for pattern, path, want in cases:
            got = solution.matches(pattern, path)
            assert got is want, "args=%r got=%r want=%r" % ((pattern, path), got, want)
    _bank_entry(solution)


def check_h04_double_star_in_the_middle():
    # anchor_kind: contract
    # anchor: A segment that is exactly `**` matches zero or more whole segments.
    # derivation: with a literal segment on each side the double star has to stretch to
    # whatever lies between them, and stop where the literal does not fit.


    def _bank_entry(solution):
        cases = [("a/**/z", "a/b/c/d/z", True), ("a/**/z", "a/z", True),
                 ("a/**/z", "a/b/c", False), ("a/**/z", "b/c/z", False)]
        for pattern, path, want in cases:
            got = solution.matches(pattern, path)
            assert got is want, "args=%r got=%r want=%r" % ((pattern, path), got, want)
    _bank_entry(solution)


def check_h05_class_and_range():
    # anchor_kind: goal
    # anchor: a way to say "one of these characters" or "any character in this range"
    # derivation: a listed set and a range each match exactly one character, and a
    # class matches nothing outside itself.


    def _bank_entry(solution):
        cases = [("v[123]", "v2", True), ("v[123]", "v4", False), ("v[123]", "v23", False),
                 ("[a-f]og", "cog", True), ("[a-f]og", "log", False),
                 ("[a-cx-z]1", "y1", True)]
        for pattern, path, want in cases:
            got = solution.matches(pattern, path)
            assert got is want, "args=%r got=%r want=%r" % ((pattern, path), got, want)
    _bank_entry(solution)


def check_h06_negated_class():
    # anchor_kind: goal
    # anchor: including the negative form
    # derivation: a leading exclamation mark inside the brackets flips the class, and it
    # still stands for exactly one character.


    def _bank_entry(solution):
        cases = [("x[!0-9]", "xa", True), ("x[!0-9]", "x5", False),
                 ("[!a]bc", "zbc", True), ("[!a]bc", "abc", False),
                 ("x[!0-9]", "x", False)]
        for pattern, path, want in cases:
            got = solution.matches(pattern, path)
            assert got is want, "args=%r got=%r want=%r" % ((pattern, path), got, want)
    _bank_entry(solution)


def check_h07_whole_path_only():
    # anchor_kind: goal
    # anchor: A pattern has to match the whole path: half a match is not a match.
    # derivation: a pattern that fits the start, or the end, or the middle of a path is
    # not a match unless it fits all of it.


    def _bank_entry(solution):
        cases = [("main", "main.py", False), ("main.py", "src/main.py", False),
                 ("src", "src/main.py", False), ("ain.py", "main.py", False),
                 ("main.py", "main.py", True)]
        for pattern, path, want in cases:
            got = solution.matches(pattern, path)
            assert got is want, "args=%r got=%r want=%r" % ((pattern, path), got, want)
    _bank_entry(solution)


def check_h08_metacharacters_are_literal():
    # anchor_kind: goal
    # anchor: Characters that mean something to a regular expression -- a dot, a plus, a
    # bracket sitting in a file name -- are ordinary characters in a path.
    # derivation: a dot in a pattern matches only a dot, and a plus or a parenthesis in
    # a file name is matched by writing it out.


    def _bank_entry(solution):
        cases = [("a.py", "axpy", False), ("a.py", "a.py", True),
                 ("c++/main.cc", "c++/main.cc", True), ("c++/main.cc", "cxx/main.cc", False),
                 ("re(1).txt", "re(1).txt", True), ("a|b", "a|b", True), ("a|b", "a", False)]
        for pattern, path, want in cases:
            got = solution.matches(pattern, path)
            assert got is want, "args=%r got=%r want=%r" % ((pattern, path), got, want)
    _bank_entry(solution)


def check_h09_selection_keeps_file_order():
    # anchor_kind: goal
    # anchor: The answer comes back in the order the files were listed, with nothing
    # listed twice.
    # derivation: two patterns that pick overlapping sets, written in the opposite order
    # to the file list, still answer in file-list order and list nothing twice.


    def _bank_entry(solution):
        paths = ["a.py", "b.txt", "c.py", "d.md", "e.py"]
        got = solution.select(["*.py", "*.py", "*.md"], paths)
        want = ["a.py", "c.py", "d.md", "e.py"]
        assert got == want, "args=%r got=%r want=%r" % (paths, got, want)
    _bank_entry(solution)


def check_h10_exclamation_removes():
    # anchor_kind: goal
    # anchor: a pattern beginning with an exclamation mark removes what the earlier ones
    # picked up
    # derivation: the removal applies to what has already been chosen, and leaves the
    # rest in place and in order.


    def _bank_entry(solution):
        paths = ["src/a.py", "src/b.py", "src/test_a.py", "src/test_b.py"]
        got = solution.select(["src/*.py", "!src/test_*.py"], paths)
        want = ["src/a.py", "src/b.py"]
        assert got == want, "args=%r got=%r want=%r" % (paths, got, want)
    _bank_entry(solution)


def check_h11_later_pattern_puts_it_back():
    # anchor_kind: goal
    # anchor: and a later pattern can put something back
    # derivation: patterns are read left to right, so an add after a removal wins, and
    # the same pair in the other order does not.


    def _bank_entry(solution):
        paths = ["a/x.py", "a/y.py", "b/x.py"]
        got = solution.select(["**/*.py", "!a/*.py", "a/y.py"], paths)
        want = ["a/y.py", "b/x.py"]
        assert got == want, "args=%r got=%r want=%r" % (paths, got, want)

        got = solution.select(["**/*.py", "a/y.py", "!a/*.py"], paths)
        want = ["b/x.py"]
        assert got == want, "args=%r got=%r want=%r" % (paths, got, want)
    _bank_entry(solution)


def check_h12_every_pattern_is_checked():
    # anchor_kind: contract
    # anchor: `select` checks every pattern it is given, whether or not anything matches
    # it.
    # derivation: a malformed pattern raises even when the file list is empty, and even
    # when it sits behind an exclamation mark.


    def _bank_entry(solution):
        for patterns in (["*.py", "src/[abc.py"], ["!src/[].py"], ["[!].py"]):
            try:
                solution.select(patterns, [])
            except ValueError:
                continue
            raise AssertionError("args=%r got=%r want=%r" % (patterns, "answered", "ValueError"))
    _bank_entry(solution)


def check_h13_nothing_selected():
    # anchor_kind: contract
    # anchor: A plain pattern adds every path that matches it
    # derivation: patterns that match nothing give an empty answer, and an empty list of
    # patterns selects nothing at all.


    def _bank_entry(solution):
        paths = ["a.py", "b.py"]
        assert solution.select([], paths) == [], (
            "args=%r got=%r want=%r" % (paths, solution.select([], paths), []))
        assert solution.select(["*.md"], paths) == [], (
            "args=%r got=%r want=%r" % (paths, solution.select(["*.md"], paths), []))
        assert solution.select(["!*.py"], paths) == [], (
            "args=%r got=%r want=%r" % (paths, solution.select(["!*.py"], paths), []))
    _bank_entry(solution)
