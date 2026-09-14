# anchor_kind: goal
# anchor: The values they use are text, whole numbers, decimals, true and false, and
# lists of one of those.
# derivation: each kind arrives as its own Python type, and true is a boolean rather
# than the word.


def run(solution):
    text = 's = "x"\ni = -12\nf = -0.5\nt = true\nlist = [1, 2, 3]\n'
    got = solution.parse(text)
    kinds = [type(got[name]).__name__ for name in ("s", "i", "f", "t", "list")]
    want = ["str", "int", "float", "bool", "list"]
    assert kinds == want, "args=%r got=%r want=%r" % (text, kinds, want)
    assert got["i"] == -12 and got["f"] == -0.5 and got["t"] is True, (
        "args=%r got=%r want=%r" % (text, (got["i"], got["f"], got["t"]), (-12, -0.5, True)))
