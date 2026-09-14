"""ow_17_diffpatch — hidden checks, 12. **Never enters a workspace.**

Generated from bank/ow_17_diffpatch/hidden/*.py by export_bank.py; the
anchor table is in ANCHORS.md beside this file.
"""
import solution


def check_h01_one_piece_per_place():
    # anchor_kind: goal
    # anchor: one per place that changed, so that a reviewer sees the two lines that
    # moved rather than one block covering everything between them
    # derivation: two edits far apart give two pieces, each holding only its own changed
    # line, not one piece spanning the untouched middle.


    def _bank_entry(solution):
        old = ["l%d" % index for index in range(10)]
        new = list(old)
        new[2] = "TWO"
        new[7] = "SEVEN"
        pieces = solution.diff(old, new)
        assert len(pieces) == 2, "args=%r got=%r want=%r" % ((old, new), pieces, "two pieces")
        want = [{"start": 2, "old": ["l2"], "new": ["TWO"]},
                {"start": 7, "old": ["l7"], "new": ["SEVEN"]}]
        assert pieces == want, "args=%r got=%r want=%r" % ((old, new), pieces, want)
    _bank_entry(solution)


def check_h02_no_unchanged_lines_at_the_edges():
    # anchor_kind: goal
    # anchor: A piece must not carry lines that did not change: not at its start, not at
    # its end.
    # derivation: across several shapes of edit, no piece with lines on both sides ever
    # begins or ends with the same line on both sides.


    def _bank_entry(solution):
        cases = [(["a", "b", "c"], ["a", "x", "c"]),
                 (["a", "b", "c", "d"], ["a", "b", "x", "y", "d"]),
                 (["p", "q", "r", "s", "t"], ["p", "Q", "r", "S", "t"]),
                 (["1", "2", "3"], ["0", "1", "2", "3", "4"])]
        for old, new in cases:
            for piece in solution.diff(old, new):
                removed, added = piece["old"], piece["new"]
                assert removed or added, "args=%r got=%r want=%r" % ((old, new), piece, "not empty")
                if removed and added:
                    assert removed[0] != added[0], (
                        "args=%r got=%r want=%r" % ((old, new), piece, "trimmed at the front"))
                    assert removed[-1] != added[-1], (
                        "args=%r got=%r want=%r" % ((old, new), piece, "trimmed at the back"))
    _bank_entry(solution)


def check_h03_pieces_are_ordered_and_apart():
    # anchor_kind: contract
    # anchor: ordered by `start`, with at least one unchanged line between the end of
    # one piece and the start of the next
    # derivation: over a version with several scattered edits the pieces come back in
    # order and never touch each other.


    def _bank_entry(solution):
        old = ["x%d" % index for index in range(20)]
        new = list(old)
        for index in (1, 5, 6, 13, 18):
            new[index] = "EDIT%d" % index
        pieces = solution.diff(old, new)
        reach = -1
        for piece in pieces:
            assert piece["start"] > reach, (
                "args=%r got=%r want=%r" % ("five scattered edits", piece["start"],
                                            "after the previous piece plus a gap"))
            reach = piece["start"] + len(piece["old"])
        assert solution.apply(old, pieces) == new, (
            "args=%r got=%r want=%r" % ("five scattered edits", solution.apply(old, pieces), new))
    _bank_entry(solution)


def check_h04_insertions():
    # anchor_kind: contract
    # anchor: Either side may be empty, but not both.
    # derivation: a pure insertion has an empty old side, and it works at the front, in
    # the middle and at the end.


    def _bank_entry(solution):
        cases = [(["b", "c"], ["a", "b", "c"]),
                 (["a", "c"], ["a", "b", "c"]),
                 (["a", "b"], ["a", "b", "c"])]
        for old, new in cases:
            pieces = solution.diff(old, new)
            assert any(piece["old"] == [] for piece in pieces), (
                "args=%r got=%r want=%r" % ((old, new), pieces, "a piece with an empty old side"))
            got = solution.apply(old, pieces)
            assert got == new, "args=%r got=%r want=%r" % ((old, new), got, new)
    _bank_entry(solution)


def check_h05_deletions():
    # anchor_kind: contract
    # anchor: `apply(old, diff(old, new))` equals `new`, for any two lists.
    # derivation: a pure deletion has an empty new side, and removing a run of lines
    # still goes out and back.


    def _bank_entry(solution):
        cases = [(["a", "b", "c"], ["a", "c"]),
                 (["a", "b", "c", "d", "e"], ["a", "e"]),
                 (["a", "b"], ["a"]),
                 (["a", "b"], ["b"])]
        for old, new in cases:
            pieces = solution.diff(old, new)
            assert any(piece["new"] == [] for piece in pieces), (
                "args=%r got=%r want=%r" % ((old, new), pieces, "a piece with an empty new side"))
            got = solution.apply(old, pieces)
            assert got == new, "args=%r got=%r want=%r" % ((old, new), got, new)
    _bank_entry(solution)


def check_h06_nothing_changed():
    # anchor_kind: goal
    # anchor: A file that did not change at all produces no pieces.
    # derivation: two equal versions give an empty list, and applying an empty list
    # gives back an equal but separate list.


    def _bank_entry(solution):
        old = ["a", "b", "c"]
        pieces = solution.diff(old, list(old))
        assert pieces == [], "args=%r got=%r want=%r" % (old, pieces, [])
        got = solution.apply(old, [])
        assert got == old, "args=%r got=%r want=%r" % (old, got, old)
        assert got is not old, "args=%r got=%r want=%r" % (old, "the same list", "a new list")
    _bank_entry(solution)


def check_h07_piece_that_does_not_fit():
    # anchor_kind: goal
    # anchor: Applying a list of pieces to a version they do not fit is the dangerous
    # case
    # derivation: a piece whose old side is not what the text holds at that index is
    # refused, and nothing partial is returned.


    def _bank_entry(solution):
        old = ["a", "b", "c"]
        for piece in ({"start": 1, "old": ["x"], "new": ["y"]},
                      {"start": 0, "old": ["a", "x"], "new": ["z"]},
                      {"start": 2, "old": ["b"], "new": ["q"]}):
            try:
                solution.apply(old, [piece])
            except ValueError:
                continue
            raise AssertionError("args=%r got=%r want=%r" % (piece, "patched", "ValueError"))
    _bank_entry(solution)


def check_h08_out_of_order_or_overlapping():
    # anchor_kind: goal
    # anchor: a list of pieces that is out of order, that overlaps itself
    # derivation: pieces given back to front, and pieces whose ranges run into each
    # other, are both refused even though each one on its own would fit.


    def _bank_entry(solution):
        old = ["a", "b", "c", "d", "e"]
        backwards = [{"start": 3, "old": ["d"], "new": ["D"]},
                     {"start": 1, "old": ["b"], "new": ["B"]}]
        overlapping = [{"start": 1, "old": ["b", "c"], "new": ["X"]},
                       {"start": 2, "old": ["c"], "new": ["Y"]}]
        for hunks in (backwards, overlapping):
            try:
                solution.apply(old, hunks)
            except ValueError:
                continue
            raise AssertionError("args=%r got=%r want=%r" % (hunks, "patched", "ValueError"))
    _bank_entry(solution)


def check_h09_malformed_piece():
    # anchor_kind: goal
    # anchor: or that is simply malformed
    # derivation: a missing key, an extra key, a piece empty on both sides, and a piece
    # reaching past the end are each refused.


    def _bank_entry(solution):
        old = ["a", "b", "c"]
        for hunk in ({"start": 0, "old": ["a"]},
                     {"start": 0, "old": ["a"], "new": ["A"], "extra": 1},
                     {"start": 1, "old": [], "new": []},
                     {"start": 2, "old": ["c", "d"], "new": ["z"]},
                     {"start": 9, "old": ["a"], "new": ["b"]},
                     ["not", "a", "dict"]):
            try:
                solution.apply(old, [hunk])
            except ValueError:
                continue
            raise AssertionError("args=%r got=%r want=%r" % (hunk, "patched", "ValueError"))
    _bank_entry(solution)


def check_h10_inputs_are_untouched():
    # anchor_kind: goal
    # anchor: Applying must not touch what it was given, because they keep the old
    # version around.
    # derivation: after a successful apply the old list and the pieces hold exactly what
    # they held before, and the answer is a different object.


    def _bank_entry(solution):
        old = ["a", "b", "c", "d"]
        new = ["a", "B", "c", "D"]
        pieces = solution.diff(old, new)
        old_before = list(old)
        pieces_before = [dict(piece) for piece in pieces]
        got = solution.apply(old, pieces)
        assert old == old_before, "args=%r got=%r want=%r" % ("apply", old, old_before)
        assert pieces == pieces_before, "args=%r got=%r want=%r" % ("apply", pieces, pieces_before)
        assert got is not old, "args=%r got=%r want=%r" % ("apply", "the same list", "a new list")
        assert got == new, "args=%r got=%r want=%r" % ((old, new), got, new)
    _bank_entry(solution)


def check_h11_empty_versions():
    # anchor_kind: contract
    # anchor: for any two lists
    # derivation: an empty old version and an empty new version are both ordinary
    # cases, and the round trip holds for them too.


    def _bank_entry(solution):
        cases = [([], ["a", "b"]), (["a", "b"], []), ([], [])]
        for old, new in cases:
            pieces = solution.diff(old, new)
            got = solution.apply(old, pieces)
            assert got == new, "args=%r got=%r want=%r" % ((old, new), got, new)
    _bank_entry(solution)


def check_h12_repeated_lines():
    # anchor_kind: goal
    # anchor: Files with many identical lines are common in their data, and going out
    # and back has to survive them.
    # derivation: versions made almost entirely of one repeated line still go out and
    # back exactly, whether a copy is added or removed.


    def _bank_entry(solution):
        cases = [(["x"] * 6, ["x"] * 7),
                 (["x"] * 6, ["x"] * 5),
                 (["x", "x", "y", "x", "x"], ["x", "x", "z", "x", "x"]),
                 (["a", "a", "b", "a", "a", "b"], ["a", "b", "a", "a", "b", "b"])]
        for old, new in cases:
            pieces = solution.diff(old, new)
            got = solution.apply(old, pieces)
            assert got == new, "args=%r got=%r want=%r" % ((old, new), got, new)
    _bank_entry(solution)
