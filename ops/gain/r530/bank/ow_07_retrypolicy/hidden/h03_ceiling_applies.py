# anchor_kind: goal
# anchor: The delay must stop growing once it reaches a ceiling they set
# derivation: once the doubling passes the ceiling every later wait is the ceiling
# exactly, never more.


def run(solution):
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
