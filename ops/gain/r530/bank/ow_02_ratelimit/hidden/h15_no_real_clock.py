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


def run(solution):
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
