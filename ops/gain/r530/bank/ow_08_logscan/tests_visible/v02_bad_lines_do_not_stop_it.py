"""Visible check 2: garbled lines are counted and the run keeps going."""


def run(solution):
    lines = [
        "2026-09-13T11:00:00Z GET /x 200 5",
        "this line is truncat",
        "2026-09-13T11:00:01Z GET /x 200 7",
    ]
    got = solution.summarize(lines)
    assert got["bad_lines"] == 1, "args=%r got=%r want=%r" % (lines, got["bad_lines"], 1)
    assert got["total"] == 3, "args=%r got=%r want=%r" % (lines, got["total"], 3)
    assert got["endpoints"][0]["n"] == 2, (
        "args=%r got=%r want=%r" % (lines, got["endpoints"][0]["n"], 2))

if __name__ == "__main__":
    import os, sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    import solution
    run(solution)
    print("PASS v02_bad_lines_do_not_stop_it")
