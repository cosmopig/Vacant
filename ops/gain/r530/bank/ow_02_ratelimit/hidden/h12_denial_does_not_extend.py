# anchor_kind: contract
# anchor: A denied call records nothing, so being denied ten times in a row leaves
# the same state as being denied once.
# derivation: hammering while blocked must not push the wait further out, and the
# door must open at the same moment either way.


class Clock(object):
    def __init__(self, t=0.0):
        self.t = t

    def __call__(self):
        return self.t


def run(solution):
    clock = Clock(0.0)
    limiter = solution.RateLimiter(10.0, 1, clock)
    limiter.allow("h")
    for moment in (1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0):
        clock.t = moment
        limiter.allow("h")
    clock.t = 9.0
    got = limiter.retry_after("h")
    assert abs(got - 1.0) < 1e-9, "args=%r got=%r want=%r" % ("retry_after after nine denials", got, 1.0)
    clock.t = 10.0
    got = limiter.allow("h")
    assert got is True, "args=%r got=%r want=%r" % ("allow at 10.0 after nine denials", got, True)
