"""Visible check 3: the path, oldest first, starting where it began."""

SPEC = {"a": {"go": "b"}, "b": {"go": "c"}, "c": {}}


def run(solution):
    machine = solution.Machine(SPEC, "a")
    machine.fire("go")
    machine.fire("go")
    got = machine.history()
    want = ["a", "b", "c"]
    assert got == want, "args=%r got=%r want=%r" % ("two moves from a", got, want)

if __name__ == "__main__":
    import os, sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    import solution
    run(solution)
    print("PASS v03_the_path_it_took")
