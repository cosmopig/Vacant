# anchor_kind: goal
# anchor: pre-release builds being treated as newer than the real thing
# derivation: for the same three numbers the plain release is the newer of the two,
# whatever the pre-release is called.


def run(solution):
    for pre in ("1.2.3-alpha", "1.2.3-zzz", "1.2.3-9999"):
        got = solution.compare(pre, "1.2.3")
        assert got == -1, "args=%r got=%r want=%r" % ((pre, "1.2.3"), got, -1)
