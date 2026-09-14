# anchor_kind: goal
# anchor: they want a nonsensical configuration to fail at construction rather than
# at the first request
# derivation: the error has to arrive from the constructor, before any call to
# allow is made.


class Clock(object):
    def __call__(self):
        return 0.0


def run(solution):
    for window, budget in ((0.0, 5), (-0.5, 5), (10.0, -1), (-1.0, -1)):
        try:
            solution.RateLimiter(window, budget, Clock())
        except ValueError:
            continue
        raise AssertionError("args=%r got=%r want=%r"
                             % ((window, budget), "constructed fine", "ValueError"))
