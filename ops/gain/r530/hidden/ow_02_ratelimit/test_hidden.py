"""ow_02_ratelimit — 隱藏驗收，15 條。**永遠不進工作區。**

對照表在 `ops/gain/r530/hidden/ow_02_ratelimit/ANCHORS.md`。
"""
import math

import solution


class FakeClock:
    def __init__(self, t=0.0):
        self.t = float(t)

    def __call__(self):
        return self.t


def _rl(window_s, max_events, t0=0.0):
    clock = FakeClock(t0)
    return solution.RateLimiter(window_s, max_events, clock), clock


def check_boundary_event_exactly_window_old_has_fallen_out():
    rl, clock = _rl(10.0, 1, 0.0)
    assert rl.allow("k") is True
    clock.t = 10.0                      # 事件時間 0 == now - window_s ⇒ 已落出
    assert rl.allow("k") is True, \
        "the window is left-open: an event exactly window_s old has fallen out"


def check_boundary_event_just_inside_window_still_counts():
    rl, clock = _rl(10.0, 1, 0.0)
    assert rl.allow("k") is True
    clock.t = 9.999                     # 事件時間 0 > now - window_s = -0.001 ⇒ 還在
    assert rl.allow("k") is False, \
        "an event that is not yet window_s old still counts"


def check_max_events_zero_blocks_everything():
    rl, _clock = _rl(5.0, 0, 0.0)
    assert rl.allow("k") is False, "max_events=0 means nothing is ever allowed"
    assert math.isinf(rl.retry_after("k")), \
        "when nothing can ever be allowed, retry_after is float('inf')"


def check_three_keys_do_not_share_a_budget():
    rl, _clock = _rl(5.0, 2, 0.0)
    for key in ("a", "b", "c"):
        assert rl.allow(key) is True
        assert rl.allow(key) is True
        assert rl.allow(key) is False, f"key {key!r} should be at its own limit"
    assert rl.allow("d") is True, "a fourth key still starts empty"


def check_retry_after_decreases_as_time_passes():
    rl, clock = _rl(10.0, 1, 0.0)
    rl.allow("k")
    assert rl.allow("k") is False
    first = rl.retry_after("k")
    clock.t = 4.0
    second = rl.retry_after("k")
    assert second < first, \
        f"retry_after must shrink as time passes: {first!r} then {second!r}"
    assert abs(second - 6.0) < 1e-9, \
        f"at t=4 with one event at t=0 and window 10, retry_after is 6.0, got {second!r}"


def check_retry_after_is_zero_for_an_unseen_key():
    rl, _clock = _rl(10.0, 1, 0.0)
    assert rl.retry_after("never-seen") == 0.0, \
        "a key with no events can be served right now"


def check_retry_after_is_zero_while_still_allowed():
    rl, _clock = _rl(10.0, 3, 0.0)
    rl.allow("k")
    assert rl.retry_after("k") == 0.0, \
        "retry_after is 0.0 whenever allow() would return True"


def check_reset_one_key_only():
    rl, _clock = _rl(10.0, 1, 0.0)
    rl.allow("a")
    rl.allow("b")
    rl.reset("a")
    assert rl.allow("a") is True, "reset('a') forgets the events under 'a'"
    assert rl.allow("b") is False, "reset('a') must not touch 'b'"


def check_reset_all_keys():
    rl, _clock = _rl(10.0, 1, 0.0)
    rl.allow("a")
    rl.allow("b")
    rl.reset()
    assert rl.allow("a") is True and rl.allow("b") is True, \
        "reset() with no argument forgets every key"


def check_clock_going_backwards_does_not_count_future_events():
    rl, clock = _rl(10.0, 1, 100.0)
    assert rl.allow("k") is True        # 事件在 t=100
    clock.t = 50.0                      # 時鐘倒退
    assert rl.allow("k") is True, \
        "an event with a timestamp later than now is outside (now - window_s, now]"


def check_blocked_calls_do_not_extend_the_window():
    rl, clock = _rl(10.0, 1, 0.0)
    assert rl.allow("k") is True
    clock.t = 5.0
    for _ in range(5):
        assert rl.allow("k") is False   # 這五次都不該被記下來
    clock.t = 10.0                      # 唯一的事件（t=0）此刻落出
    assert rl.allow("k") is True, \
        "allow() records an event only when it returns True"


def check_small_float_window():
    rl, clock = _rl(0.1, 2, 0.0)
    assert rl.allow("k") is True
    clock.t = 0.05
    assert rl.allow("k") is True
    assert rl.allow("k") is False
    clock.t = 0.1000001
    assert rl.allow("k") is True, \
        "the event at t=0 has fallen out of a 0.1 s window by t=0.1000001"


def check_window_not_positive_raises():
    for bad in (0.0, -1.0):
        try:
            solution.RateLimiter(bad, 1, FakeClock(0.0))
        except ValueError:
            pass
        else:
            raise AssertionError(f"window_s={bad!r} must raise ValueError")


def check_negative_max_events_raises():
    try:
        solution.RateLimiter(1.0, -1, FakeClock(0.0))
    except ValueError:
        pass
    else:
        raise AssertionError("max_events=-1 must raise ValueError")


def check_allow_returns_a_real_bool():
    rl, _clock = _rl(10.0, 1, 0.0)
    first = rl.allow("k")
    second = rl.allow("k")
    assert isinstance(first, bool) and isinstance(second, bool), \
        f"allow() must return bool, got {type(first).__name__}/{type(second).__name__}"
