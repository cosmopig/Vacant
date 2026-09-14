# anchor_kind: goal
# anchor: Text sometimes has to contain quotes, tabs and line breaks, written with a
# backslash.
# derivation: the four escapes turn into the characters they stand for, and nothing
# else does.


def run(solution):
    text = 'a = "he said \\"no\\""\nb = "one\\ttwo"\nc = "line\\nline"\nd = "a\\\\b"\n'
    got = solution.parse(text)
    want = {"a": 'he said "no"', "b": "one\ttwo", "c": "line\nline", "d": "a\\b"}
    assert got == want, "args=%r got=%r want=%r" % (text, got, want)
