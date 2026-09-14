# anchor_kind: goal
# anchor: A width that makes no sense should be refused.
# derivation: zero and negative widths raise rather than looping or returning
# something arbitrary.


def run(solution):
    for width in (0, -1, -100):
        try:
            solution.reflow("some words here", width)
        except ValueError:
            continue
        raise AssertionError("args=%r got=%r want=%r" % (width, "wrapped", "ValueError"))
