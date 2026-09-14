# anchor_kind: goal
# anchor: it deals in fractions of a second
# derivation: a window shorter than a second has to behave exactly like a long
# one, including the moment it expires.


class Clock(object):
    def __init__(self, t=0.0):
        self.t = t

    def __call__(self):
        return self.t


def run(solution):
    clock = Clock(0.0)
    limiter = solution.RateLimiter(0.25, 2, clock)
    got = []
    for moment in (0.0, 0.1, 0.2, 0.26):
        clock.t = moment
        got.append(limiter.allow("f"))
    assert got == [True, True, False, True], (
        "args=%r got=%r want=%r" % ("window 0.25 at 0, .1, .2, .26", got, [True, True, False, True]))
