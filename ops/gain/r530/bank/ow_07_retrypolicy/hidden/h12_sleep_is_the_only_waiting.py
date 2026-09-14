# anchor_kind: goal
# anchor: Their tests must run instantly, so waiting has to be something they can
# substitute.
# derivation: with the real clock made unavailable the helper still has to work,
# which is only true when every pause goes through the injected callable.

import time


def _boom(*_a, **_kw):
    raise RuntimeError("the real sleep is off limits")


def run(solution):
    naps = []
    calls = []

    def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise ConnectionError("flap")
        return "fine"

    saved = time.sleep
    time.sleep = _boom
    try:
        got = solution.retry(flaky, attempts=5, backoff_s=60.0, max_backoff_s=600.0,
                             retry_on=(ConnectionError,), sleep=naps.append)
    except RuntimeError:
        raise AssertionError("args=%r got=%r want=%r"
                             % ("flaky with backoff 60s", "called time.sleep",
                                "called the injected sleep"))
    finally:
        time.sleep = saved
    assert got == "fine", "args=%r got=%r want=%r" % ("flaky with backoff 60s", got, "fine")
    assert naps == [60.0, 120.0], (
        "args=%r got=%r want=%r" % ("flaky with backoff 60s", naps, [60.0, 120.0]))
