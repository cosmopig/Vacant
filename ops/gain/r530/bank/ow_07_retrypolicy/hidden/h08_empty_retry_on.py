# anchor_kind: contract
# anchor: An empty `retry_on` therefore retries nothing.
# derivation: with no retryable kinds at all the first failure is the last one.


def run(solution):
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
