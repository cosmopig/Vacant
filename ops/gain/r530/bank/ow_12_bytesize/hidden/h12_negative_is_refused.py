# anchor_kind: goal
# anchor: a negative size
# derivation: a minus sign is refused when reading and when printing, rather than
# producing a negative byte count.


def run(solution):
    for text in ("-1", "-1 KiB", "- 5 MB"):
        try:
            solution.to_bytes(text)
        except ValueError:
            continue
        raise AssertionError("args=%r got=%r want=%r" % (text, "a number", "ValueError"))
    for number in (-1, -1024):
        try:
            solution.humanize(number)
        except ValueError:
            continue
        raise AssertionError("args=%r got=%r want=%r" % (number, "a string", "ValueError"))
