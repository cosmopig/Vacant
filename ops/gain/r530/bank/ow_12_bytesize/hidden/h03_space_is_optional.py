# anchor_kind: goal
# anchor: sometimes leave a space before it and sometimes not
# derivation: none, one or several spaces between the number and the unit all read
# the same, and padding around the whole string is ignored.


def run(solution):
    for text in ("4KiB", "4 KiB", "4    KiB", "  4KiB  ", "\t4 KiB\n"):
        got = solution.to_bytes(text)
        assert got == 4096, "args=%r got=%r want=%r" % (text, got, 4096)
