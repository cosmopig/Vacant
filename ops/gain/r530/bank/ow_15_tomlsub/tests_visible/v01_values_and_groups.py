"""Visible check 1: the five kinds of value, and a group."""


def run(solution):
    text = 'name = "billing"\nport = 8080\nratio = 0.25\ndebug = false\n\n[db]\nhost = "db.internal"\n'
    got = solution.parse(text)
    want = {"name": "billing", "port": 8080, "ratio": 0.25, "debug": False,
            "db": {"host": "db.internal"}}
    assert got == want, "args=%r got=%r want=%r" % (text, got, want)
    assert isinstance(got["port"], int) and got["debug"] is False, (
        "args=%r got=%r want=%r" % (text, (type(got["port"]).__name__, got["debug"]), ("int", False)))

if __name__ == "__main__":
    import os, sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    import solution
    run(solution)
    print("PASS v01_values_and_groups")
