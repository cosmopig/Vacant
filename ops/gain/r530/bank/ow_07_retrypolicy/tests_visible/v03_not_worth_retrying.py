"""Visible check 3: a failure outside the listed kinds comes straight back."""


def run(solution):
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

if __name__ == "__main__":
    import os, sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    import solution
    run(solution)
    print("PASS v03_not_worth_retrying")
