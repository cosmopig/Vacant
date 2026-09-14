# anchor_kind: contract
# anchor: Names before the first heading live at the top level.
# derivation: a name written above every heading stays at the top, and the same name
# inside a group is a different setting.


def run(solution):
    text = 'host = "top"\n\n[db]\nhost = "inner"\n'
    got = solution.parse(text)
    want = {"host": "top", "db": {"host": "inner"}}
    assert got == want, "args=%r got=%r want=%r" % (text, got, want)
