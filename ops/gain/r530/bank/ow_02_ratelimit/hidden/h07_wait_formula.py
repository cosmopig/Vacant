# anchor_kind: contract
# anchor: it returns `leaving + window_s - now`, where `leaving` is the earliest
# counted event that has to fall out of the window before the next call can be
# admitted
# derivation: with a budget of two and events at 0 and 1, the first one leaving is
# the one at 0, so at now=3 with a window of 5 the wait is exactly 2.0.


class Clock(object):
    def __init__(self, t=0.0):
        self.t = t

    def __call__(self):
        return self.t


def run(solution):
    clock = Clock(0.0)
    limiter = solution.RateLimiter(5.0, 2, clock)
    limiter.allow("q")
    clock.t = 1.0
    limiter.allow("q")
    clock.t = 3.0
    assert limiter.allow("q") is False, "args=%r got=%r want=%r" % ("allow at 3.0", True, False)
    got = limiter.retry_after("q")
    assert abs(got - 2.0) < 1e-9, "args=%r got=%r want=%r" % ("retry_after at 3.0", got, 2.0)
