"""Visible check 2: byte counts turn back into the written forms."""


def run(solution):
    cases = [(1536, True, "1.5 KiB"), (1500000, False, "1.5 MB"), (3 * 1024 ** 3, True, "3.0 GiB")]
    for number, binary, want in cases:
        got = solution.humanize(number, binary=binary)
        assert got == want, "args=%r got=%r want=%r" % ((number, binary), got, want)

if __name__ == "__main__":
    import os, sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    import solution
    run(solution)
    print("PASS v02_prints_sizes")
