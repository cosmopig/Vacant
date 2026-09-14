"""Visible check 1: the three numbers sort as numbers, not as text."""


def run(solution):
    cases = [("1.10.0", "1.9.0", 1), ("1.9.0", "1.10.0", -1), ("2.0.0", "2.0.0", 0),
             ("1.2.3", "1.2.4", -1), ("10.0.0", "9.99.99", 1)]
    for a, b, want in cases:
        got = solution.compare(a, b)
        assert got == want, "args=%r got=%r want=%r" % ((a, b), got, want)

if __name__ == "__main__":
    import os, sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    import solution
    run(solution)
    print("PASS v01_numbers_are_numbers")
