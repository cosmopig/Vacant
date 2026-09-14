"""Visible check 2: retry_after is zero while admitted and positive once denied;
a nonsensical configuration fails at construction."""


class Clock(object):
    def __init__(self, t=0.0):
        self.t = t

    def __call__(self):
        return self.t


def run(solution):
    clock = Clock()
    limiter = solution.RateLimiter(4.0, 1, clock)
    got = limiter.retry_after("u")
    assert got == 0.0, "args=%r got=%r want=%r" % ("retry_after('u') before any call", got, 0.0)
    assert limiter.allow("u") is True, "args=%r got=%r want=%r" % ("allow('u')", False, True)
    assert limiter.allow("u") is False, "args=%r got=%r want=%r" % ("allow('u') again", True, False)
    got = limiter.retry_after("u")
    assert got > 0.0, "args=%r got=%r want=%r" % ("retry_after('u') once denied", got, "> 0.0")

    for bad in ((0.0, 1), (-3.0, 1), (5.0, -1)):
        try:
            solution.RateLimiter(bad[0], bad[1], clock)
        except ValueError:
            continue
        raise AssertionError("args=%r got=%r want=%r" % (bad, "no error", "ValueError"))

if __name__ == "__main__":
    import os, sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    import solution
    run(solution)
    print("PASS v02_retry_after_and_config")
