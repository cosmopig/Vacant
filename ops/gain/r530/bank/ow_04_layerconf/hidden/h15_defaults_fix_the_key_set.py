# anchor_kind: contract
# anchor: `defaults` fixes both the set of keys and the type of each value.
# derivation: as_dict() has exactly the default keys, no more and no fewer, and a
# value's type follows the default even when the file offers something else.


def run(solution):
    defaults = {"n": 0, "s": "", "f": 0.0, "b": False}
    file_text = "n = 5\ns = 5\nf = 5\nb = 1\nextra = 5\n"
    got = solution.load(defaults, file_text, {"APP_ALSO_EXTRA": "5"}).as_dict()
    assert sorted(got) == ["b", "f", "n", "s"], (
        "args=%r got=%r want=%r" % (file_text, sorted(got), ["b", "f", "n", "s"]))
    kinds = [type(got[k]).__name__ for k in ("n", "s", "f", "b")]
    want = ["int", "str", "float", "bool"]
    assert kinds == want, "args=%r got=%r want=%r" % (file_text, kinds, want)
