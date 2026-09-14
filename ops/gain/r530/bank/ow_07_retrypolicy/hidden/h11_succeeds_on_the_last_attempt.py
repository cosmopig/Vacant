# anchor_kind: contract
# anchor: `retry` returns the value of the first call that returns.
# derivation: a call that only works on the final allowed attempt still returns its
# value, having waited exactly once per earlier failure.


def run(solution):
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
