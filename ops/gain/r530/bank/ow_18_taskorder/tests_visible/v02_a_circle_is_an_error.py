"""Visible check 2: a table that can never be run is reported."""


def run(solution):
    jobs = {"a": ["b"], "b": ["a"]}
    try:
        solution.plan(jobs)
    except ValueError:
        return
    raise AssertionError("args=%r got=%r want=%r" % (jobs, "an order", "ValueError"))

if __name__ == "__main__":
    import os, sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    import solution
    run(solution)
    print("PASS v02_a_circle_is_an_error")
