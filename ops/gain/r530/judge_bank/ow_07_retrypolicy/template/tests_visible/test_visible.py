"""Checks that ship with this task. You can run them yourself: `sh run_tests.sh`.

Each `check_*` function is one check. A check passes when it returns
normally. These are the same checks the client runs before accepting
the work.
"""
import solution


def check_v01_retries_then_succeeds():
    """Visible check 1: a call that settles down on the third try returns its value."""


    def _bank_entry(solution):
        calls = []
        naps = []

        def flaky():
            calls.append(1)
            if len(calls) < 3:
                raise ConnectionError("not yet")
            return "payload"

        got = solution.retry(flaky, attempts=5, backoff_s=0.5, max_backoff_s=30.0,
                             retry_on=(ConnectionError,), sleep=naps.append)
        assert got == "payload", "args=%r got=%r want=%r" % ("flaky, attempts=5", got, "payload")
        assert len(calls) == 3, "args=%r got=%r want=%r" % ("flaky, attempts=5", len(calls), 3)
        assert len(naps) == 2, "args=%r got=%r want=%r" % ("flaky, attempts=5", naps, "two waits")
    _bank_entry(solution)


def check_v02_backs_off_longer():
    """Visible check 2: the wait grows between attempts, and there is one wait
    fewer than there are attempts."""


    def _bank_entry(solution):
        naps = []

        def always_fails():
            raise TimeoutError("nope")

        try:
            solution.retry(always_fails, attempts=4, backoff_s=1.0, max_backoff_s=1000.0,
                           retry_on=(TimeoutError,), sleep=naps.append)
        except TimeoutError:
            pass
        else:
            raise AssertionError("args=%r got=%r want=%r" % ("always_fails", "returned", "TimeoutError"))
        assert len(naps) == 3, "args=%r got=%r want=%r" % ("attempts=4", naps, "three waits")
        assert naps == sorted(naps) and naps[0] < naps[-1], (
            "args=%r got=%r want=%r" % ("attempts=4", naps, "a growing sequence"))
    _bank_entry(solution)


def check_v03_not_worth_retrying():
    """Visible check 3: a failure outside the listed kinds comes straight back."""


    def _bank_entry(solution):
        calls = []
        naps = []

        def wrong_kind():
            calls.append(1)
            raise ValueError("bad argument")

        try:
            solution.retry(wrong_kind, attempts=5, backoff_s=1.0, max_backoff_s=10.0,
                           retry_on=(ConnectionError,), sleep=naps.append)
        except ValueError:
            pass
        else:
            raise AssertionError("args=%r got=%r want=%r" % ("wrong_kind", "returned", "ValueError"))
        assert len(calls) == 1, "args=%r got=%r want=%r" % ("wrong_kind", len(calls), 1)
        assert naps == [], "args=%r got=%r want=%r" % ("wrong_kind", naps, [])
    _bank_entry(solution)
