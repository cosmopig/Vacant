# anchor_kind: goal
# anchor: a `#` inside a piece of text is not a comment
# derivation: a hash inside quotes belongs to the value, while a hash after the
# value still ends the line.


def run(solution):
    text = 'colour = "#ff0000"   # the brand red\ntag = "a#b#c"\n'
    got = solution.parse(text)
    want = {"colour": "#ff0000", "tag": "a#b#c"}
    assert got == want, "args=%r got=%r want=%r" % (text, got, want)
