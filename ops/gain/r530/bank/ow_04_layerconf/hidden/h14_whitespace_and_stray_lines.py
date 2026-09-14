# anchor_kind: contract
# anchor: A line that is neither of those and contains no `=` is ignored. The value
# is everything after the first `=`, with surrounding whitespace removed.
# derivation: padding around the key and the value disappears, and a junk line with
# no equals sign does not derail the rest of the file.


def run(solution):
    defaults = {"a": "1", "b": 2}
    file_text = "   a    =    hello   \nthis line is junk\n\tb\t=\t7\t\n"
    got = solution.load(defaults, file_text, {}).as_dict()
    want = {"a": "hello", "b": 7}
    assert got == want, "args=%r got=%r want=%r" % (file_text, got, want)
