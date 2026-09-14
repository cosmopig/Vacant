# anchor_kind: contract
# anchor: a key that has never been seen has no events
# derivation: an unknown caller starts with a full budget and a wait of zero.


class Clock(object):
    def __call__(self):
        return 3.5


def run(solution):
    limiter = solution.RateLimiter(2.0, 3, Clock())
    got = limiter.retry_after("brand-new")
    assert got == 0.0, "args=%r got=%r want=%r" % ("retry_after('brand-new')", got, 0.0)
    got = limiter.allow("brand-new")
    assert got is True, "args=%r got=%r want=%r" % ("allow('brand-new')", got, True)
