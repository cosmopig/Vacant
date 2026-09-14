"""Visible check 2: one changed line gives one piece holding just that line."""


def run(solution):
    old = ["a", "b", "c", "d", "e"]
    new = ["a", "b", "CHANGED", "d", "e"]
    pieces = solution.diff(old, new)
    assert len(pieces) == 1, "args=%r got=%r want=%r" % ((old, new), pieces, "one piece")
    piece = pieces[0]
    assert sorted(piece) == ["new", "old", "start"], (
        "args=%r got=%r want=%r" % ((old, new), sorted(piece), ["new", "old", "start"]))
    want = {"start": 2, "old": ["c"], "new": ["CHANGED"]}
    assert piece == want, "args=%r got=%r want=%r" % ((old, new), piece, want)

if __name__ == "__main__":
    import os, sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    import solution
    run(solution)
    print("PASS v02_shape_of_a_piece")
