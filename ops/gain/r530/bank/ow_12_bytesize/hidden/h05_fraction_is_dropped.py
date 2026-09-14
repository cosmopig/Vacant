# anchor_kind: goal
# anchor: the fraction is dropped rather than rounded up
# derivation: a value whose product has a fraction truncates downward, so 2.9
# bytes is 2 bytes and not 3.


def run(solution):
    cases = [("2.9", 2), ("0.9 B", 0), ("1.75 KiB", 1792), ("0.0009 KB", 0)]
    for text, want in cases:
        got = solution.to_bytes(text)
        assert got == want, "args=%r got=%r want=%r" % (text, got, want)
