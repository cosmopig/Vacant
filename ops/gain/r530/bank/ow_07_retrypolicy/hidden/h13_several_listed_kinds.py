# anchor_kind: contract
# anchor: An exception that is not an instance of any type in `retry_on` is raised
# onward at once
# derivation: with two kinds listed, both are retried and a third one still escapes
# on the spot.


def run(solution):
    calls = []
    naps = []
    failures = [TimeoutError("a"), ConnectionError("b"), KeyError("c")]

    def mixed():
        calls.append(1)
        raise failures[len(calls) - 1]

    try:
        solution.retry(mixed, attempts=9, backoff_s=1.0, max_backoff_s=8.0,
                       retry_on=(TimeoutError, ConnectionError), sleep=naps.append)
    except KeyError:
        assert (len(calls), naps) == (3, [1.0, 2.0]), (
            "args=%r got=%r want=%r" % ("timeout, connection, key",
                                        (len(calls), naps), (3, [1.0, 2.0])))
        return
    raise AssertionError("args=%r got=%r want=%r" % ("timeout, connection, key", "returned", "KeyError"))
