# anchor_kind: goal
# anchor: The same setting written twice in one group
# derivation: the second appearance raises on its own line, while the same name in
# two different groups is fine.


def run(solution):
    text = '[db]\nport = 1\nhost = "h"\nport = 2\n'
    try:
        solution.parse(text)
    except ValueError as exc:
        assert str(exc).startswith("line 4: "), (
            "args=%r got=%r want=%r" % (text, str(exc), "line 4: ..."))
    else:
        raise AssertionError("args=%r got=%r want=%r" % (text, "parsed", "ValueError"))

    fine = '[a]\nport = 1\n\n[b]\nport = 2\n'
    got = solution.parse(fine)
    assert got == {"a": {"port": 1}, "b": {"port": 2}}, (
        "args=%r got=%r want=%r" % (fine, got, {"a": {"port": 1}, "b": {"port": 2}}))
