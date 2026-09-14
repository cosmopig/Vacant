"""Visible check 2: can() answers before the fact, and a refusal changes nothing."""

SPEC = {"draft": {"submit": "review"}, "review": {"approve": "done"}, "done": {}}


def run(solution):
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

if __name__ == "__main__":
    import os, sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    import solution
    run(solution)
    print("PASS v02_asking_first_and_being_refused")
