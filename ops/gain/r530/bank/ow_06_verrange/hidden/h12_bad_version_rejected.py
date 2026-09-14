# anchor_kind: goal
# anchor: A version string or a requirement they cannot make sense of has to be
# rejected rather than guessed at
# derivation: a version that is not three numbers with an optional pre-release
# raises from both entry points instead of comparing as something.


def run(solution):
    for text in ("1.2", "1.2.3.4", "v1.2.3", "1.2.x", "", "1.2.3-"):
        try:
            solution.compare(text, "1.0.0")
        except ValueError:
            pass
        else:
            raise AssertionError("args=%r got=%r want=%r" % (text, "compared fine", "ValueError"))
        try:
            solution.satisfies(text, ">=1.0.0")
        except ValueError:
            continue
        raise AssertionError("args=%r got=%r want=%r" % (text, "answered fine", "ValueError"))
