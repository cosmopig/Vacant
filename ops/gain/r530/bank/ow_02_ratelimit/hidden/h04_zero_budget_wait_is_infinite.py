# anchor_kind: contract
# anchor: When `max_events` is 0 no wait ever helps, so `retry_after` returns
# `float("inf")`.
# derivation: the answer to "how long until yes" has no finite value when the
# answer is never yes.


class Clock(object):
    def __call__(self):
        return 12.0


def run(solution):
    limiter = solution.RateLimiter(3.0, 0, Clock())
    got = limiter.retry_after("z")
    assert got == float("inf"), "args=%r got=%r want=%r" % ("max_events=0", got, float("inf"))
