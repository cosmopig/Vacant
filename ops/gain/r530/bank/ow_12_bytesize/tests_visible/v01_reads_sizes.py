"""Visible check 1: the written forms turn into byte counts."""


def run(solution):
    cases = [("1.5 KiB", 1536), ("10MB", 10000000), ("512", 512), ("3 b", 3)]
    for text, want in cases:
        got = solution.to_bytes(text)
        assert got == want, "args=%r got=%r want=%r" % (text, got, want)

if __name__ == "__main__":
    import os, sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    import solution
    run(solution)
    print("PASS v01_reads_sizes")
