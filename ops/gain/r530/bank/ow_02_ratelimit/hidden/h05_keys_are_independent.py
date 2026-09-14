# anchor_kind: goal
# anchor: counted separately per caller
# derivation: one caller exhausting the budget must leave the others untouched.


class Clock(object):
    def __init__(self, t=0.0):
        self.t = t

    def __call__(self):
        return self.t


def run(solution):
    clock = Clock(50.0)
    limiter = solution.RateLimiter(30.0, 2, clock)
    for _ in range(5):
        limiter.allow("noisy")
    got = [limiter.allow("quiet"), limiter.allow("quiet"), limiter.allow("quiet")]
    assert got == [True, True, False], (
        "args=%r got=%r want=%r" % ("quiet after noisy burns its budget", got, [True, True, False]))
    assert limiter.retry_after("fresh") == 0.0, (
        "args=%r got=%r want=%r" % ("retry_after('fresh')", limiter.retry_after("fresh"), 0.0))
