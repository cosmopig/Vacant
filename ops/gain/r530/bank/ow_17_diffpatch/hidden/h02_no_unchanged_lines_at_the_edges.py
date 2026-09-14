# anchor_kind: goal
# anchor: A piece must not carry lines that did not change: not at its start, not at
# its end.
# derivation: across several shapes of edit, no piece with lines on both sides ever
# begins or ends with the same line on both sides.


def run(solution):
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
