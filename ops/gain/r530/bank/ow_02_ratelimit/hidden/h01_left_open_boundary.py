# anchor_kind: contract
# anchor: an event counts while it falls in `(now - window_s, now]`, left open and
# right closed
# derivation: an event sitting exactly window_s ago is on the open side, so it no
# longer counts and the next call is admitted.


class Clock(object):
    def __init__(self, t=0.0):
        self.t = t

    def __call__(self):
        return self.t


def run(solution):
    clock = Clock(0.0)
    limiter = solution.RateLimiter(5.0, 1, clock)
    limiter.allow("k")
    clock.t = 5.0
    got = limiter.allow("k")
    assert got is True, "args=%r got=%r want=%r" % ("event at 0.0, allow at 5.0, window 5.0", got, True)
