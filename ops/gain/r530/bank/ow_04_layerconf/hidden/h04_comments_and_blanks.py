# anchor_kind: goal
# anchor: half of it is comments
# derivation: comment lines and blank lines carry no setting, and a comment sitting
# above a key must not swallow it.


def run(solution):
    defaults = {"a": 1, "b": 2}
    file_text = "# a is the first one\n\n   # indented comment\na = 10\n\nb = 20\n"
    config = solution.load(defaults, file_text, {})
    got = config.as_dict()
    want = {"a": 10, "b": 20}
    assert got == want, "args=%r got=%r want=%r" % (file_text, got, want)
