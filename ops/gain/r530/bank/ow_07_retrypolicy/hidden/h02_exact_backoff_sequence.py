# anchor_kind: contract
# anchor: the helper waits `min(backoff_s * 2 ** (k - 1), max_backoff_s)` seconds
# derivation: the first wait is the base delay itself, not the doubled one, so the
# sequence from a base of 0.5 is 0.5, 1.0, 2.0, 4.0.


def run(solution):
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
