# anchor_kind: contract
# anchor: `allow(key)` returns True when the number of counted events for that key
# is below `max_events`
# derivation: with a budget of zero no count is ever below it, so nothing is ever
# admitted, on any key, at any time.


class Clock(object):
    def __init__(self, t=0.0):
        self.t = t

    def __call__(self):
        return self.t


def run(solution):
    clock = Clock(0.0)
    limiter = solution.RateLimiter(1.0, 0, clock)
    got = []
    for moment in (0.0, 7.0, 900.0):
        clock.t = moment
        got.append(limiter.allow("anyone"))
    assert got == [False, False, False], (
        "args=%r got=%r want=%r" % ("max_events=0", got, [False, False, False]))
