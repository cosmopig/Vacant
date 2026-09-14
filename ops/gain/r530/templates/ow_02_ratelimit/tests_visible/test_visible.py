"""Checks that ship with this task. You can run them yourself: `bash run_tests.sh`.

Each `check_*` function is one check. A check passes when it returns normally.
These are the same checks the client runs before accepting the work.
"""
import solution


class FakeClock:
    def __init__(self, t=0.0):
        self.t = float(t)

    def __call__(self):
        return self.t


def check_allows_then_blocks():
    clock = FakeClock(100.0)
    rl = solution.RateLimiter(10.0, 2, clock)
    assert rl.allow("a") is True, "the first request in an empty window is allowed"
    assert rl.allow("a") is True, "the second request is still inside max_events=2"
    assert rl.allow("a") is False, "the third request in the same window is refused"


def check_retry_after_then_allowed_again():
    clock = FakeClock(100.0)
    rl = solution.RateLimiter(10.0, 1, clock)
    assert rl.allow("a") is True
    assert rl.allow("a") is False
    wait = rl.retry_after("a")
    assert abs(wait - 10.0) < 1e-9, \
        f"after one event at t=100 with window 10, retry_after should be 10.0, got {wait!r}"
    clock.t = 100.0 + wait
    assert rl.allow("a") is True, \
        "once retry_after seconds have passed the request must be allowed again"


def check_keys_are_independent():
    clock = FakeClock(0.0)
    rl = solution.RateLimiter(5.0, 1, clock)
    assert rl.allow("a") is True
    assert rl.allow("a") is False
    assert rl.allow("b") is True, "key 'b' has its own window"
