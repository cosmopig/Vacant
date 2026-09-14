"""Visible check 1: nothing runs before something it waits for."""


def run(solution):
    jobs = {"deploy": ["test"], "test": ["build"], "build": []}
    got = solution.plan(jobs)
    assert sorted(got) == ["build", "deploy", "test"], (
        "args=%r got=%r want=%r" % (jobs, sorted(got), ["build", "deploy", "test"]))
    assert got.index("build") < got.index("test") < got.index("deploy"), (
        "args=%r got=%r want=%r" % (jobs, got, "build before test before deploy"))

if __name__ == "__main__":
    import os, sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    import solution
    run(solution)
    print("PASS v01_prerequisites_come_first")
