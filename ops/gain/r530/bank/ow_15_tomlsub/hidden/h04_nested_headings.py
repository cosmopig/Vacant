# anchor_kind: goal
# anchor: headings can be nested with dots
# derivation: a dotted heading puts the names one level deeper, and the parent group
# is created on the way.


def run(solution):
    text = '[a]\nx = 1\n\n[a.b]\ny = 2\n\n[a.b.c]\nz = 3\n'
    got = solution.parse(text)
    want = {"a": {"x": 1, "b": {"y": 2, "c": {"z": 3}}}}
    assert got == want, "args=%r got=%r want=%r" % (text, got, want)
