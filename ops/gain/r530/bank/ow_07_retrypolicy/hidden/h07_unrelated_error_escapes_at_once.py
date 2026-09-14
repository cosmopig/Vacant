# anchor_kind: goal
# anchor: A failure that is not worth retrying has to come straight back out,
# immediately, with no pause at all.
# derivation: an error outside the listed kinds ends the run after one call, with
# no wait, even when many attempts were allowed.


def run(solution):
    calls = []
    naps = []

    def fails():
        calls.append(1)
        raise ZeroDivisionError("no")

    try:
        solution.retry(fails, attempts=9, backoff_s=2.0, max_backoff_s=9.0,
                       retry_on=(TimeoutError, ConnectionError), sleep=naps.append)
    except ZeroDivisionError:
        assert (len(calls), naps) == (1, []), (
            "args=%r got=%r want=%r" % ("ZeroDivisionError, retry_on timeouts",
                                        (len(calls), naps), (1, [])))
        return
    raise AssertionError("args=%r got=%r want=%r" % ("ZeroDivisionError", "returned", "it"))
