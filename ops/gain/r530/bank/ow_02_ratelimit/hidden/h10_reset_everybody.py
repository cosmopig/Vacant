# anchor_kind: goal
# anchor: or for everybody, without rebuilding the limiter
# derivation: the no-argument wipe has to clear every caller at once, and the same
# limiter object keeps working afterwards.


class Clock(object):
    def __call__(self):
        return 4.0


def run(solution):
    limiter = solution.RateLimiter(9.0, 1, Clock())
    for who in ("a", "b", "c"):
        limiter.allow(who)
    limiter.reset()
    got = [limiter.allow(who) for who in ("a", "b", "c")]
    assert got == [True, True, True], (
        "args=%r got=%r want=%r" % ("allow after reset()", got, [True, True, True]))
    limiter.reset(None)
    got = limiter.allow("a")
    assert got is True, "args=%r got=%r want=%r" % ("allow('a') after reset(None)", got, True)
