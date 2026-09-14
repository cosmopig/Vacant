# anchor_kind: contract
# anchor: `retry` returns the value of the first call that returns.
# derivation: when nothing fails the helper calls once, returns that value and
# never waits.


def run(solution):
    calls = []
    naps = []
    got = solution.retry(lambda: (calls.append(1), {"ok": True})[1],
                         attempts=3, backoff_s=1.0, max_backoff_s=5.0,
                         retry_on=(Exception,), sleep=naps.append)
    assert got == {"ok": True}, "args=%r got=%r want=%r" % ("a call that works", got, {"ok": True})
    assert (len(calls), naps) == (1, []), (
        "args=%r got=%r want=%r" % ("a call that works", (len(calls), naps), (1, [])))
