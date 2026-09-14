# anchor_kind: contract
# anchor: A clock that moves backwards is not an error: events lying in the future
# are simply outside `(now - window_s, now]`.
# derivation: after the test clock is rewound past the recorded events, those
# events are in the future, count for nothing, and nothing raises.


class Clock(object):
    def __init__(self, t=0.0):
        self.t = t

    def __call__(self):
        return self.t


def run(solution):
    clock = Clock(100.0)
    limiter = solution.RateLimiter(10.0, 1, clock)
    limiter.allow("r")
    clock.t = 50.0
    got = limiter.allow("r")
    assert got is True, "args=%r got=%r want=%r" % ("allow at 50.0 after an event at 100.0", got, True)
    got = limiter.retry_after("nobody")
    assert got == 0.0, "args=%r got=%r want=%r" % ("retry_after('nobody') on a rewound clock", got, 0.0)
