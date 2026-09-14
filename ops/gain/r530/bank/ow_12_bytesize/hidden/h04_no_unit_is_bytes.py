# anchor_kind: goal
# anchor: A size with no unit at all is a count of bytes.
# derivation: a bare number and the same number with the byte unit in either case
# all mean the same thing.


def run(solution):
    for text in ("777", "777B", "777 b", "777 B"):
        got = solution.to_bytes(text)
        assert got == 777, "args=%r got=%r want=%r" % (text, got, 777)
