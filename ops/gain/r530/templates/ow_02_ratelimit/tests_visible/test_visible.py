"""Checks that ship with this task. You can run them yourself: `sh run_tests.sh`.

Each `check_*` function is one check. A check passes when it returns
normally. These are the same checks the client runs before accepting
the work.
"""
import solution


def check_v01_window_and_keys():
    """Visible check 1: the window slides, and callers are counted apart."""


    class Clock(object):
        def __init__(self, t=0.0):
            self.t = t

        def __call__(self):
            return self.t


    def _bank_entry(solution):
        clock = Clock()
        limiter = solution.RateLimiter(10.0, 2, clock)
        seen = []
        for moment in (0.0, 1.0, 2.0):
            clock.t = moment
            seen.append(limiter.allow("alice"))
        want = [True, True, False]
        assert seen == want, "args=%r got=%r want=%r" % ("allow('alice') at 0,1,2", seen, want)

        clock.t = 2.0
        got = limiter.allow("bob")
        assert got is True, "args=%r got=%r want=%r" % ("allow('bob') at 2.0", got, True)

        clock.t = 11.0
        got = limiter.allow("alice")
        assert got is True, "args=%r got=%r want=%r" % ("allow('alice') at 11.0", got, True)
    _bank_entry(solution)


def check_v02_retry_after_and_config():
    """Visible check 2: retry_after is zero while admitted and positive once denied;
    a nonsensical configuration fails at construction."""


    class Clock(object):
        def __init__(self, t=0.0):
            self.t = t

        def __call__(self):
            return self.t


    def _bank_entry(solution):
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
    _bank_entry(solution)


def check_v03_reset():
    """Visible check 3: wiping one caller, and wiping everybody."""


    class Clock(object):
        def __init__(self, t=0.0):
            self.t = t

        def __call__(self):
            return self.t


    def _bank_entry(solution):
        clock = Clock(100.0)
        limiter = solution.RateLimiter(60.0, 1, clock)
        limiter.allow("x")
        limiter.allow("y")
        limiter.reset("x")
        got = limiter.allow("x")
        assert got is True, "args=%r got=%r want=%r" % ("allow('x') after reset('x')", got, True)
        got = limiter.allow("y")
        assert got is False, "args=%r got=%r want=%r" % ("allow('y') after reset('x')", got, False)

        limiter.reset()
        got = [limiter.allow("x"), limiter.allow("y")]
        assert got == [True, True], "args=%r got=%r want=%r" % ("allow after reset()", got, [True, True])
    _bank_entry(solution)
