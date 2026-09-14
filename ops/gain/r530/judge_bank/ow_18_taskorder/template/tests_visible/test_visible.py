"""Checks that ship with this task. You can run them yourself: `sh run_tests.sh`.

Each `check_*` function is one check. A check passes when it returns
normally. These are the same checks the client runs before accepting
the work.
"""
import solution


def check_v01_prerequisites_come_first():
    """Visible check 1: nothing runs before something it waits for."""


    def _bank_entry(solution):
        jobs = {"deploy": ["test"], "test": ["build"], "build": []}
        got = solution.plan(jobs)
        assert sorted(got) == ["build", "deploy", "test"], (
            "args=%r got=%r want=%r" % (jobs, sorted(got), ["build", "deploy", "test"]))
        assert got.index("build") < got.index("test") < got.index("deploy"), (
            "args=%r got=%r want=%r" % (jobs, got, "build before test before deploy"))
    _bank_entry(solution)


def check_v02_a_circle_is_an_error():
    """Visible check 2: a table that can never be run is reported."""


    def _bank_entry(solution):
        jobs = {"a": ["b"], "b": ["a"]}
        try:
            solution.plan(jobs)
        except ValueError:
            return
        raise AssertionError("args=%r got=%r want=%r" % (jobs, "an order", "ValueError"))
    _bank_entry(solution)
