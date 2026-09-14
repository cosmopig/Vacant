# anchor_kind: contract
# anchor: it raises `ValueError` naming the state and the event
# derivation: the message has to carry the state the order is in and the event that
# was asked for, so a support ticket can be answered from the log alone.

SPEC = {"paid": {"ship": "shipped"}, "shipped": {}}


def run(solution):
    machine = solution.Machine(SPEC, "paid")
    try:
        machine.fire("cancel")
    except ValueError as exc:
        text = str(exc)
        assert "paid" in text and "cancel" in text, (
            "args=%r got=%r want=%r" % ("fire('cancel') in paid", text, "a message naming paid and cancel"))
        return
    raise AssertionError("args=%r got=%r want=%r" % ("fire('cancel') in paid", "moved", "ValueError"))
