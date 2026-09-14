"""ow_07_retrypolicy — hidden checks, 13. **Never enters a workspace.**

Generated from bank/ow_07_retrypolicy/hidden/*.py by export_bank.py; the
anchor table is in ANCHORS.md beside this file.
"""
import solution


def check_h01_first_call_wins():
    # anchor_kind: contract
    # anchor: `retry` returns the value of the first call that returns.
    # derivation: when nothing fails the helper calls once, returns that value and
    # never waits.


    def _bank_entry(solution):
        calls = []
        naps = []
        got = solution.retry(lambda: (calls.append(1), {"ok": True})[1],
                             attempts=3, backoff_s=1.0, max_backoff_s=5.0,
                             retry_on=(Exception,), sleep=naps.append)
        assert got == {"ok": True}, "args=%r got=%r want=%r" % ("a call that works", got, {"ok": True})
        assert (len(calls), naps) == (1, []), (
            "args=%r got=%r want=%r" % ("a call that works", (len(calls), naps), (1, [])))
    _bank_entry(solution)


def check_h02_exact_backoff_sequence():
    # anchor_kind: contract
    # anchor: the helper waits `min(backoff_s * 2 ** (k - 1), max_backoff_s)` seconds
    # derivation: the first wait is the base delay itself, not the doubled one, so the
    # sequence from a base of 0.5 is 0.5, 1.0, 2.0, 4.0.


    def _bank_entry(solution):
        naps = []

        def fails():
            raise OSError("down")

        try:
            solution.retry(fails, attempts=5, backoff_s=0.5, max_backoff_s=1000.0,
                           retry_on=(OSError,), sleep=naps.append)
        except OSError:
            pass
        want = [0.5, 1.0, 2.0, 4.0]
        assert naps == want, "args=%r got=%r want=%r" % ("backoff_s=0.5, attempts=5", naps, want)
    _bank_entry(solution)


def check_h03_ceiling_applies():
    # anchor_kind: goal
    # anchor: The delay must stop growing once it reaches a ceiling they set
    # derivation: once the doubling passes the ceiling every later wait is the ceiling
    # exactly, never more.


    def _bank_entry(solution):
        naps = []

        def fails():
            raise OSError("down")

        try:
            solution.retry(fails, attempts=6, backoff_s=1.0, max_backoff_s=3.0,
                           retry_on=(OSError,), sleep=naps.append)
        except OSError:
            pass
        want = [1.0, 2.0, 3.0, 3.0, 3.0]
        assert naps == want, "args=%r got=%r want=%r" % ("backoff 1.0, ceiling 3.0", naps, want)
    _bank_entry(solution)


def check_h04_no_trailing_wait():
    # anchor_kind: goal
    # anchor: they do not want to sit through a pause that leads nowhere
    # derivation: the number of waits is one fewer than the number of attempts, because
    # the wait after the final failure would lead to no further call.


    def _bank_entry(solution):
        for attempts in (2, 3, 7):
            naps = []
            calls = []

            def fails():
                calls.append(1)
                raise KeyError("k")

            try:
                solution.retry(fails, attempts=attempts, backoff_s=0.1, max_backoff_s=100.0,
                               retry_on=(KeyError,), sleep=naps.append)
            except KeyError:
                pass
            assert (len(calls), len(naps)) == (attempts, attempts - 1), (
                "args=%r got=%r want=%r" % (attempts, (len(calls), len(naps)),
                                            (attempts, attempts - 1)))
    _bank_entry(solution)


def check_h05_original_error_object():
    # anchor_kind: goal
    # anchor: they want the original error, not something the helper wrapped around it
    # derivation: the object that comes out is the very object the last call raised, so
    # the caller's own attributes on it survive.


    class Flaky(RuntimeError):
        pass


    def _bank_entry(solution):
        mine = Flaky("the real one")
        mine.detail = 7

        def fails():
            raise mine

        try:
            solution.retry(fails, attempts=3, backoff_s=0.0, max_backoff_s=0.0,
                           retry_on=(Flaky,), sleep=lambda _s: None)
        except BaseException as got:
            assert got is mine, "args=%r got=%r want=%r" % ("a Flaky instance", got, mine)
            assert getattr(got, "detail", None) == 7, (
                "args=%r got=%r want=%r" % ("a Flaky instance", getattr(got, "detail", None), 7))
            return
        raise AssertionError("args=%r got=%r want=%r" % ("a Flaky instance", "returned", "Flaky"))
    _bank_entry(solution)


def check_h06_subclass_counts():
    # anchor_kind: goal
    # anchor: A subclass of a listed error counts as that error.
    # derivation: listing the base class is enough, so a derived failure is retried
    # rather than escaping on the first attempt.


    class Base(Exception):
        pass


    class Derived(Base):
        pass


    def _bank_entry(solution):
        calls = []

        def flaky():
            calls.append(1)
            if len(calls) < 3:
                raise Derived("child")
            return "done"

        got = solution.retry(flaky, attempts=4, backoff_s=0.0, max_backoff_s=0.0,
                             retry_on=(Base,), sleep=lambda _s: None)
        assert got == "done", "args=%r got=%r want=%r" % ("Derived raised, Base listed", got, "done")
        assert len(calls) == 3, "args=%r got=%r want=%r" % ("Derived raised, Base listed", len(calls), 3)
    _bank_entry(solution)


def check_h07_unrelated_error_escapes_at_once():
    # anchor_kind: goal
    # anchor: A failure that is not worth retrying has to come straight back out,
    # immediately, with no pause at all.
    # derivation: an error outside the listed kinds ends the run after one call, with
    # no wait, even when many attempts were allowed.


    def _bank_entry(solution):
        calls = []
        naps = []

        def fails():
            calls.append(1)
            raise ZeroDivisionError("no")

        try:
            solution.retry(fails, attempts=9, backoff_s=2.0, max_backoff_s=9.0,
                           retry_on=(TimeoutError, ConnectionError), sleep=naps.append)
        except ZeroDivisionError:
            assert (len(calls), naps) == (1, []), (
                "args=%r got=%r want=%r" % ("ZeroDivisionError, retry_on timeouts",
                                            (len(calls), naps), (1, [])))
            return
        raise AssertionError("args=%r got=%r want=%r" % ("ZeroDivisionError", "returned", "it"))
    _bank_entry(solution)


def check_h08_empty_retry_on():
    # anchor_kind: contract
    # anchor: An empty `retry_on` therefore retries nothing.
    # derivation: with no retryable kinds at all the first failure is the last one.


    def _bank_entry(solution):
        calls = []
        naps = []

        def fails():
            calls.append(1)
            raise RuntimeError("first and only")

        try:
            solution.retry(fails, attempts=6, backoff_s=1.0, max_backoff_s=1.0,
                           retry_on=(), sleep=naps.append)
        except RuntimeError:
            assert (len(calls), naps) == (1, []), (
                "args=%r got=%r want=%r" % ("retry_on=()", (len(calls), naps), (1, [])))
            return
        raise AssertionError("args=%r got=%r want=%r" % ("retry_on=()", "returned", "RuntimeError"))
    _bank_entry(solution)


def check_h09_attempts_must_be_at_least_one():
    # anchor_kind: goal
    # anchor: Asking for fewer than one attempt is a programming mistake and should be
    # caught before anything is called.
    # derivation: the ValueError arrives without fn having run, for zero and for
    # negative counts alike.


    def _bank_entry(solution):
        for attempts in (0, -1, -10):
            calls = []

            def fn():
                calls.append(1)
                return 1

            try:
                solution.retry(fn, attempts=attempts, backoff_s=1.0, max_backoff_s=1.0,
                               retry_on=(Exception,), sleep=lambda _s: None)
            except ValueError:
                assert calls == [], "args=%r got=%r want=%r" % (attempts, calls, [])
                continue
            raise AssertionError("args=%r got=%r want=%r" % (attempts, "no error", "ValueError"))
    _bank_entry(solution)


def check_h10_single_attempt():
    # anchor_kind: contract
    # anchor: `fn` is called at most `attempts` times.
    # derivation: one attempt means one call, no wait, and the failure straight out,
    # even though the failure is a retryable kind.


    def _bank_entry(solution):
        calls = []
        naps = []

        def fails():
            calls.append(1)
            raise ConnectionError("once")

        try:
            solution.retry(fails, attempts=1, backoff_s=5.0, max_backoff_s=5.0,
                           retry_on=(ConnectionError,), sleep=naps.append)
        except ConnectionError:
            assert (len(calls), naps) == (1, []), (
                "args=%r got=%r want=%r" % ("attempts=1", (len(calls), naps), (1, [])))
            return
        raise AssertionError("args=%r got=%r want=%r" % ("attempts=1", "returned", "ConnectionError"))
    _bank_entry(solution)


def check_h11_succeeds_on_the_last_attempt():
    # anchor_kind: contract
    # anchor: `retry` returns the value of the first call that returns.
    # derivation: a call that only works on the final allowed attempt still returns its
    # value, having waited exactly once per earlier failure.


    def _bank_entry(solution):
        calls = []
        naps = []

        def flaky():
            calls.append(1)
            if len(calls) < 4:
                raise TimeoutError("slow")
            return 99

        got = solution.retry(flaky, attempts=4, backoff_s=1.0, max_backoff_s=100.0,
                             retry_on=(TimeoutError,), sleep=naps.append)
        assert got == 99, "args=%r got=%r want=%r" % ("succeeds on attempt 4 of 4", got, 99)
        assert (len(calls), len(naps)) == (4, 3), (
            "args=%r got=%r want=%r" % ("succeeds on attempt 4 of 4", (len(calls), len(naps)), (4, 3)))
    _bank_entry(solution)


def check_h12_sleep_is_the_only_waiting():
    # anchor_kind: goal
    # anchor: Their tests must run instantly, so waiting has to be something they can
    # substitute.
    # derivation: with the real clock made unavailable the helper still has to work,
    # which is only true when every pause goes through the injected callable.

    import time


    def _boom(*_a, **_kw):
        raise RuntimeError("the real sleep is off limits")


    def _bank_entry(solution):
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
    _bank_entry(solution)


def check_h13_several_listed_kinds():
    # anchor_kind: contract
    # anchor: An exception that is not an instance of any type in `retry_on` is raised
    # onward at once
    # derivation: with two kinds listed, both are retried and a third one still escapes
    # on the spot.


    def _bank_entry(solution):
        calls = []
        naps = []
        failures = [TimeoutError("a"), ConnectionError("b"), KeyError("c")]

        def mixed():
            calls.append(1)
            raise failures[len(calls) - 1]

        try:
            solution.retry(mixed, attempts=9, backoff_s=1.0, max_backoff_s=8.0,
                           retry_on=(TimeoutError, ConnectionError), sleep=naps.append)
        except KeyError:
            assert (len(calls), naps) == (3, [1.0, 2.0]), (
                "args=%r got=%r want=%r" % ("timeout, connection, key",
                                            (len(calls), naps), (3, [1.0, 2.0])))
            return
        raise AssertionError("args=%r got=%r want=%r" % ("timeout, connection, key", "returned", "KeyError"))
    _bank_entry(solution)
