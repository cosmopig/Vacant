# anchor_kind: goal
# anchor: they would rather it stick out than be chopped in half
# derivation: a single long run with no spaces occupies a line of its own, whole,
# and the words around it are still wrapped normally.


def run(solution):
    long_one = "https://example.com/a/very/long/path/that/never/ends/at/all"
    text = "see %s now\n" % long_one
    got = solution.reflow(text, 20)
    lines = got.rstrip("\n").split("\n")
    assert long_one in lines, "args=%r got=%r want=%r" % (text, lines, "the long run on its own line")
