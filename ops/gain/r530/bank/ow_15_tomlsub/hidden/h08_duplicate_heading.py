# anchor_kind: goal
# anchor: or the same heading opened twice
# derivation: reopening a group raises on the line that reopened it, even when the
# names inside do not clash.


def run(solution):
    text = '[db]\nport = 1\n\n[db]\nhost = "h"\n'
    try:
        solution.parse(text)
    except ValueError as exc:
        assert str(exc).startswith("line 4: "), (
            "args=%r got=%r want=%r" % (text, str(exc), "line 4: ..."))
        return
    raise AssertionError("args=%r got=%r want=%r" % (text, "parsed", "ValueError"))
