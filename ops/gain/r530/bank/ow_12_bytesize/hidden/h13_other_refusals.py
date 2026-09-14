# anchor_kind: goal
# anchor: an empty setting, a unit nobody has heard of, two units in one string
# derivation: each named refusal is checked on its own, including a string that has
# a unit but no number.


def run(solution):
    for text in ("", "  ", "KiB", "12 XB", "3 KiB MB", "1 2 KiB", "1,5 KiB", "1e3"):
        try:
            solution.to_bytes(text)
        except ValueError:
            continue
        raise AssertionError("args=%r got=%r want=%r" % (text, "a number", "ValueError"))
