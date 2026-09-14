# anchor_kind: contract
# anchor: left open and right closed
# derivation: a hair before the window expires the event is still inside, so the
# call is still refused.


class Clock(object):
    def __init__(self, t=0.0):
        self.t = t

    def __call__(self):
        return self.t


def run(solution):
    clock = Clock(0.0)
    limiter = solution.RateLimiter(5.0, 1, clock)
    limiter.allow("k")
    clock.t = 4.999
    got = limiter.allow("k")
    assert got is False, "args=%r got=%r want=%r" % ("event at 0.0, allow at 4.999", got, False)
