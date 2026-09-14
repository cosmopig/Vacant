"""ow_02_ratelimit — hidden checks, 15. **Never enters a workspace.**

Generated from bank/ow_02_ratelimit/hidden/*.py by export_bank.py; the
anchor table is in ANCHORS.md beside this file.
"""
import solution


def check_h01_left_open_boundary():
    # anchor_kind: contract
    # anchor: an event counts while it falls in `(now - window_s, now]`, left open and
    # right closed
    # derivation: an event sitting exactly window_s ago is on the open side, so it no
    # longer counts and the next call is admitted.


    class Clock(object):
        def __init__(self, t=0.0):
            self.t = t

        def __call__(self):
            return self.t


    def _bank_entry(solution):
        clock = Clock(0.0)
        limiter = solution.RateLimiter(5.0, 1, clock)
        limiter.allow("k")
        clock.t = 5.0
        got = limiter.allow("k")
        assert got is True, "args=%r got=%r want=%r" % ("event at 0.0, allow at 5.0, window 5.0", got, True)
    _bank_entry(solution)


def check_h02_right_closed_boundary():
    # anchor_kind: contract
    # anchor: left open and right closed
    # derivation: a hair before the window expires the event is still inside, so the
    # call is still refused.


    class Clock(object):
        def __init__(self, t=0.0):
            self.t = t

        def __call__(self):
            return self.t


    def _bank_entry(solution):
        clock = Clock(0.0)
        limiter = solution.RateLimiter(5.0, 1, clock)
        limiter.allow("k")
        clock.t = 4.999
        got = limiter.allow("k")
        assert got is False, "args=%r got=%r want=%r" % ("event at 0.0, allow at 4.999", got, False)
    _bank_entry(solution)


def check_h03_zero_budget_blocks():
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


    def _bank_entry(solution):
        clock = Clock(0.0)
        limiter = solution.RateLimiter(1.0, 0, clock)
        got = []
        for moment in (0.0, 7.0, 900.0):
            clock.t = moment
            got.append(limiter.allow("anyone"))
        assert got == [False, False, False], (
            "args=%r got=%r want=%r" % ("max_events=0", got, [False, False, False]))
    _bank_entry(solution)


def check_h04_zero_budget_wait_is_infinite():
    # anchor_kind: contract
    # anchor: When `max_events` is 0 no wait ever helps, so `retry_after` returns
    # `float("inf")`.
    # derivation: the answer to "how long until yes" has no finite value when the
    # answer is never yes.


    class Clock(object):
        def __call__(self):
            return 12.0


    def _bank_entry(solution):
        limiter = solution.RateLimiter(3.0, 0, Clock())
        got = limiter.retry_after("z")
        assert got == float("inf"), "args=%r got=%r want=%r" % ("max_events=0", got, float("inf"))
    _bank_entry(solution)


def check_h05_keys_are_independent():
    # anchor_kind: goal
    # anchor: counted separately per caller
    # derivation: one caller exhausting the budget must leave the others untouched.


    class Clock(object):
        def __init__(self, t=0.0):
            self.t = t

        def __call__(self):
            return self.t


    def _bank_entry(solution):
        clock = Clock(50.0)
        limiter = solution.RateLimiter(30.0, 2, clock)
        for _ in range(5):
            limiter.allow("noisy")
        got = [limiter.allow("quiet"), limiter.allow("quiet"), limiter.allow("quiet")]
        assert got == [True, True, False], (
            "args=%r got=%r want=%r" % ("quiet after noisy burns its budget", got, [True, True, False]))
        assert limiter.retry_after("fresh") == 0.0, (
            "args=%r got=%r want=%r" % ("retry_after('fresh')", limiter.retry_after("fresh"), 0.0))
    _bank_entry(solution)


def check_h06_wait_shrinks():
    # anchor_kind: goal
    # anchor: that answer has to shrink as time passes rather than being a fixed guess
    # derivation: reading the wait at two later moments must give two smaller numbers,
    # each smaller by exactly the elapsed time.


    class Clock(object):
        def __init__(self, t=0.0):
            self.t = t

        def __call__(self):
            return self.t


    def _bank_entry(solution):
        clock = Clock(0.0)
        limiter = solution.RateLimiter(8.0, 1, clock)
        limiter.allow("s")
        clock.t = 2.0
        first = limiter.retry_after("s")
        clock.t = 5.0
        second = limiter.retry_after("s")
        assert abs(first - 6.0) < 1e-9, "args=%r got=%r want=%r" % ("retry_after at 2.0", first, 6.0)
        assert abs(second - 3.0) < 1e-9, "args=%r got=%r want=%r" % ("retry_after at 5.0", second, 3.0)
    _bank_entry(solution)


def check_h07_wait_formula():
    # anchor_kind: contract
    # anchor: it returns `leaving + window_s - now`, where `leaving` is the earliest
    # counted event that has to fall out of the window before the next call can be
    # admitted
    # derivation: with a budget of two and events at 0 and 1, the first one leaving is
    # the one at 0, so at now=3 with a window of 5 the wait is exactly 2.0.


    class Clock(object):
        def __init__(self, t=0.0):
            self.t = t

        def __call__(self):
            return self.t


    def _bank_entry(solution):
        clock = Clock(0.0)
        limiter = solution.RateLimiter(5.0, 2, clock)
        limiter.allow("q")
        clock.t = 1.0
        limiter.allow("q")
        clock.t = 3.0
        assert limiter.allow("q") is False, "args=%r got=%r want=%r" % ("allow at 3.0", True, False)
        got = limiter.retry_after("q")
        assert abs(got - 2.0) < 1e-9, "args=%r got=%r want=%r" % ("retry_after at 3.0", got, 2.0)
    _bank_entry(solution)


def check_h08_unseen_key():
    # anchor_kind: contract
    # anchor: a key that has never been seen has no events
    # derivation: an unknown caller starts with a full budget and a wait of zero.


    class Clock(object):
        def __call__(self):
            return 3.5


    def _bank_entry(solution):
        limiter = solution.RateLimiter(2.0, 3, Clock())
        got = limiter.retry_after("brand-new")
        assert got == 0.0, "args=%r got=%r want=%r" % ("retry_after('brand-new')", got, 0.0)
        got = limiter.allow("brand-new")
        assert got is True, "args=%r got=%r want=%r" % ("allow('brand-new')", got, True)
    _bank_entry(solution)


def check_h09_reset_one_caller():
    # anchor_kind: goal
    # anchor: They also want to wipe the record for one caller
    # derivation: wiping one caller clears that caller's wait and nobody else's.


    class Clock(object):
        def __call__(self):
            return 20.0


    def _bank_entry(solution):
        limiter = solution.RateLimiter(15.0, 1, Clock())
        limiter.allow("one")
        limiter.allow("two")
        limiter.reset("one")
        got = (limiter.retry_after("one"), limiter.retry_after("two"))
        assert got[0] == 0.0, "args=%r got=%r want=%r" % ("retry_after('one') after reset", got[0], 0.0)
        assert got[1] > 0.0, "args=%r got=%r want=%r" % ("retry_after('two') after reset('one')", got[1], "> 0.0")
    _bank_entry(solution)


def check_h10_reset_everybody():
    # anchor_kind: goal
    # anchor: or for everybody, without rebuilding the limiter
    # derivation: the no-argument wipe has to clear every caller at once, and the same
    # limiter object keeps working afterwards.


    class Clock(object):
        def __call__(self):
            return 4.0


    def _bank_entry(solution):
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
    _bank_entry(solution)


def check_h11_clock_rewound():
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


    def _bank_entry(solution):
        clock = Clock(100.0)
        limiter = solution.RateLimiter(10.0, 1, clock)
        limiter.allow("r")
        clock.t = 50.0
        got = limiter.allow("r")
        assert got is True, "args=%r got=%r want=%r" % ("allow at 50.0 after an event at 100.0", got, True)
        got = limiter.retry_after("nobody")
        assert got == 0.0, "args=%r got=%r want=%r" % ("retry_after('nobody') on a rewound clock", got, 0.0)
    _bank_entry(solution)


def check_h12_denial_does_not_extend():
    # anchor_kind: contract
    # anchor: A denied call records nothing, so being denied ten times in a row leaves
    # the same state as being denied once.
    # derivation: hammering while blocked must not push the wait further out, and the
    # door must open at the same moment either way.


    class Clock(object):
        def __init__(self, t=0.0):
            self.t = t

        def __call__(self):
            return self.t


    def _bank_entry(solution):
        clock = Clock(0.0)
        limiter = solution.RateLimiter(10.0, 1, clock)
        limiter.allow("h")
        for moment in (1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0):
            clock.t = moment
            limiter.allow("h")
        clock.t = 9.0
        got = limiter.retry_after("h")
        assert abs(got - 1.0) < 1e-9, "args=%r got=%r want=%r" % ("retry_after after nine denials", got, 1.0)
        clock.t = 10.0
        got = limiter.allow("h")
        assert got is True, "args=%r got=%r want=%r" % ("allow at 10.0 after nine denials", got, True)
    _bank_entry(solution)


def check_h13_fractional_seconds():
    # anchor_kind: goal
    # anchor: it deals in fractions of a second
    # derivation: a window shorter than a second has to behave exactly like a long
    # one, including the moment it expires.


    class Clock(object):
        def __init__(self, t=0.0):
            self.t = t

        def __call__(self):
            return self.t


    def _bank_entry(solution):
        clock = Clock(0.0)
        limiter = solution.RateLimiter(0.25, 2, clock)
        got = []
        for moment in (0.0, 0.1, 0.2, 0.26):
            clock.t = moment
            got.append(limiter.allow("f"))
        assert got == [True, True, False, True], (
            "args=%r got=%r want=%r" % ("window 0.25 at 0, .1, .2, .26", got, [True, True, False, True]))
    _bank_entry(solution)


def check_h14_bad_configuration():
    # anchor_kind: goal
    # anchor: they want a nonsensical configuration to fail at construction rather than
    # at the first request
    # derivation: the error has to arrive from the constructor, before any call to
    # allow is made.


    class Clock(object):
        def __call__(self):
            return 0.0


    def _bank_entry(solution):
        for window, budget in ((0.0, 5), (-0.5, 5), (10.0, -1), (-1.0, -1)):
            try:
                solution.RateLimiter(window, budget, Clock())
            except ValueError:
                continue
            raise AssertionError("args=%r got=%r want=%r"
                                 % ((window, budget), "constructed fine", "ValueError"))
    _bank_entry(solution)


def check_h15_no_real_clock():
    # anchor_kind: goal
    # anchor: the notion of now has to come from outside
    # derivation: if the real clock is unavailable the limiter must still work, which
    # is only true when the injected clock is the only source of time.

    import time


    def _boom(*_a, **_kw):
        raise RuntimeError("the real clock is off limits")


    class Clock(object):
        def __init__(self, t=0.0):
            self.t = t

        def __call__(self):
            return self.t


    def _bank_entry(solution):
        clock = Clock(0.0)
        saved = {}
        for name in ("time", "monotonic", "perf_counter"):
            saved[name] = getattr(time, name)
            setattr(time, name, _boom)
        try:
            limiter = solution.RateLimiter(6.0, 1, clock)
            first = limiter.allow("only")
            clock.t = 1.0
            second = limiter.allow("only")
            wait = limiter.retry_after("only")
        except RuntimeError:
            raise AssertionError("args=%r got=%r want=%r"
                                 % ("allow/retry_after", "read the real clock",
                                    "used only the injected clock"))
        finally:
            for name, original in saved.items():
                setattr(time, name, original)
        assert (first, second) == (True, False), (
            "args=%r got=%r want=%r" % ("allow twice", (first, second), (True, False)))
        assert abs(wait - 5.0) < 1e-9, "args=%r got=%r want=%r" % ("retry_after at 1.0", wait, 5.0)
    _bank_entry(solution)
