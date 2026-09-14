# anchor_kind: contract
# anchor: `fn` is called at most `attempts` times.
# derivation: one attempt means one call, no wait, and the failure straight out,
# even though the failure is a retryable kind.


def run(solution):
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
