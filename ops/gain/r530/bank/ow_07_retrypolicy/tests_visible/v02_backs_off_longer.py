"""Visible check 2: the wait grows between attempts, and there is one wait
fewer than there are attempts."""


def run(solution):
    naps = []

    def always_fails():
        raise TimeoutError("nope")

    try:
        solution.retry(always_fails, attempts=4, backoff_s=1.0, max_backoff_s=1000.0,
                       retry_on=(TimeoutError,), sleep=naps.append)
    except TimeoutError:
        pass
    else:
        raise AssertionError("args=%r got=%r want=%r" % ("always_fails", "returned", "TimeoutError"))
    assert len(naps) == 3, "args=%r got=%r want=%r" % ("attempts=4", naps, "three waits")
    assert naps == sorted(naps) and naps[0] < naps[-1], (
        "args=%r got=%r want=%r" % ("attempts=4", naps, "a growing sequence"))

if __name__ == "__main__":
    import os, sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    import solution
    run(solution)
    print("PASS v02_backs_off_longer")
