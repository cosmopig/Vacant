"""Visible check 3: a number from a file arrives as a number, not a string."""


def run(solution):
    defaults = {"port": 8080, "ratio": 0.5, "verbose": False, "name": "svc"}
    file_text = "port = 1234\nratio = 2.5\nverbose = true\nname = 99\n"
    config = solution.load(defaults, file_text, {})
    got = config.as_dict()
    want = {"port": 1234, "ratio": 2.5, "verbose": True, "name": "99"}
    assert got == want, "args=%r got=%r want=%r" % (file_text, got, want)
    assert isinstance(got["port"], int), (
        "args=%r got=%r want=%r" % (file_text, type(got["port"]).__name__, "int"))
    assert got["verbose"] is True, "args=%r got=%r want=%r" % (file_text, got["verbose"], True)

if __name__ == "__main__":
    import os, sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    import solution
    run(solution)
    print("PASS v03_types_follow_defaults")
