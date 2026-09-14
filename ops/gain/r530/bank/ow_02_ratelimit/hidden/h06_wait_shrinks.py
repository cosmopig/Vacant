# anchor_kind: goal
# anchor: that answer has to shrink as time passes rather than being a fixed guess
# derivation: reading the wait at two later moments must give two smaller numbers,
# each smaller by exactly the elapsed time.


class Clock(object):
    def __init__(self, t=0.0):
        self.t = t

    def __call__(self):
        return self.t


def run(solution):
    clock = Clock(0.0)
    limiter = solution.RateLimiter(8.0, 1, clock)
    limiter.allow("s")
    clock.t = 2.0
    first = limiter.retry_after("s")
    clock.t = 5.0
    second = limiter.retry_after("s")
    assert abs(first - 6.0) < 1e-9, "args=%r got=%r want=%r" % ("retry_after at 2.0", first, 6.0)
    assert abs(second - 3.0) < 1e-9, "args=%r got=%r want=%r" % ("retry_after at 5.0", second, 3.0)
