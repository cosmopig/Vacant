"""Visible check 1: an order walks the whiteboard."""

SPEC = {"new": {"pay": "paid"},
        "paid": {"ship": "shipped", "refund": "refunded"},
        "shipped": {},
        "refunded": {}}


def run(solution):
    machine = solution.Machine(SPEC, "new")
    assert machine.state == "new", "args=%r got=%r want=%r" % ("start", machine.state, "new")
    got = machine.fire("pay")
    assert got == "paid", "args=%r got=%r want=%r" % ("fire('pay')", got, "paid")
    got = machine.fire("ship")
    assert got == "shipped", "args=%r got=%r want=%r" % ("fire('ship')", got, "shipped")
    assert machine.state == "shipped", (
        "args=%r got=%r want=%r" % ("state after ship", machine.state, "shipped"))

if __name__ == "__main__":
    import os, sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    import solution
    run(solution)
    print("PASS v01_moves_the_way_the_rules_say")
