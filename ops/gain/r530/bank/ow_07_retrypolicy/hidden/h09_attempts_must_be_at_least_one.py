# anchor_kind: goal
# anchor: Asking for fewer than one attempt is a programming mistake and should be
# caught before anything is called.
# derivation: the ValueError arrives without fn having run, for zero and for
# negative counts alike.


def run(solution):
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
