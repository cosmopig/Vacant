# anchor_kind: goal
# anchor: They also want to wipe the record for one caller
# derivation: wiping one caller clears that caller's wait and nobody else's.


class Clock(object):
    def __call__(self):
        return 20.0


def run(solution):
    limiter = solution.RateLimiter(15.0, 1, Clock())
    limiter.allow("one")
    limiter.allow("two")
    limiter.reset("one")
    got = (limiter.retry_after("one"), limiter.retry_after("two"))
    assert got[0] == 0.0, "args=%r got=%r want=%r" % ("retry_after('one') after reset", got[0], 0.0)
    assert got[1] > 0.0, "args=%r got=%r want=%r" % ("retry_after('two') after reset('one')", got[1], "> 0.0")
