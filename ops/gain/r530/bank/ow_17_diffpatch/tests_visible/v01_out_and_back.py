"""Visible check 1: the pieces put back onto the old version give the new one."""


def run(solution):
    old = ["one", "two", "three", "four"]
    new = ["one", "TWO", "three", "four"]
    pieces = solution.diff(old, new)
    got = solution.apply(old, pieces)
    assert got == new, "args=%r got=%r want=%r" % ((old, new), got, new)

if __name__ == "__main__":
    import os, sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    import solution
    run(solution)
    print("PASS v01_out_and_back")
