"""Visible check 1: a call that settles down on the third try returns its value."""


def run(solution):
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

if __name__ == "__main__":
    import os, sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    import solution
    run(solution)
    print("PASS v01_retries_then_succeeds")
