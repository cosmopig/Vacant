"""Checks that ship with this task. You can run them yourself: `sh run_tests.sh`.

Each `check_*` function is one check. A check passes when it returns
normally. These are the same checks the client runs before accepting
the work.
"""
import solution


def check_v01_moves_the_way_the_rules_say():
    """Visible check 1: an order walks the whiteboard."""

    SPEC = {"new": {"pay": "paid"},
            "paid": {"ship": "shipped", "refund": "refunded"},
            "shipped": {},
            "refunded": {}}


    def _bank_entry(solution):
        machine = solution.Machine(SPEC, "new")
        assert machine.state == "new", "args=%r got=%r want=%r" % ("start", machine.state, "new")
        got = machine.fire("pay")
        assert got == "paid", "args=%r got=%r want=%r" % ("fire('pay')", got, "paid")
        got = machine.fire("ship")
        assert got == "shipped", "args=%r got=%r want=%r" % ("fire('ship')", got, "shipped")
        assert machine.state == "shipped", (
            "args=%r got=%r want=%r" % ("state after ship", machine.state, "shipped"))
    _bank_entry(solution)


def check_v02_asking_first_and_being_refused():
    """Visible check 2: can() answers before the fact, and a refusal changes nothing."""

    SPEC = {"draft": {"submit": "review"}, "review": {"approve": "done"}, "done": {}}


    def _bank_entry(solution):
        machine = solution.Machine(SPEC, "draft")
        assert machine.can("submit") is True, (
            "args=%r got=%r want=%r" % ("can('submit') in draft", machine.can("submit"), True))
        assert machine.can("approve") is False, (
            "args=%r got=%r want=%r" % ("can('approve') in draft", machine.can("approve"), False))
        try:
            machine.fire("approve")
        except ValueError:
            pass
        else:
            raise AssertionError("args=%r got=%r want=%r" % ("fire('approve') in draft", "moved", "ValueError"))
        assert machine.state == "draft", (
            "args=%r got=%r want=%r" % ("state after a refusal", machine.state, "draft"))
    _bank_entry(solution)


def check_v03_the_path_it_took():
    """Visible check 3: the path, oldest first, starting where it began."""

    SPEC = {"a": {"go": "b"}, "b": {"go": "c"}, "c": {}}


    def _bank_entry(solution):
        machine = solution.Machine(SPEC, "a")
        machine.fire("go")
        machine.fire("go")
        got = machine.history()
        want = ["a", "b", "c"]
        assert got == want, "args=%r got=%r want=%r" % ("two moves from a", got, want)
    _bank_entry(solution)
