"""Visible check 2: a pre-release is older than the release it leads up to."""


def run(solution):
    got = solution.compare("1.0.0-rc1", "1.0.0")
    assert got == -1, "args=%r got=%r want=%r" % (("1.0.0-rc1", "1.0.0"), got, -1)
    got = solution.compare("1.0.0", "1.0.0-rc1")
    assert got == 1, "args=%r got=%r want=%r" % (("1.0.0", "1.0.0-rc1"), got, 1)
    got = solution.compare("1.0.0-rc1", "1.0.0-rc1")
    assert got == 0, "args=%r got=%r want=%r" % (("1.0.0-rc1", "1.0.0-rc1"), got, 0)

if __name__ == "__main__":
    import os, sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    import solution
    run(solution)
    print("PASS v02_prerelease_is_older")
