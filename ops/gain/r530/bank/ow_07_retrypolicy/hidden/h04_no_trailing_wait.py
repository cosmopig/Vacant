# anchor_kind: goal
# anchor: they do not want to sit through a pause that leads nowhere
# derivation: the number of waits is one fewer than the number of attempts, because
# the wait after the final failure would lead to no further call.


def run(solution):
    for attempts in (2, 3, 7):
        naps = []
        calls = []

        def fails():
            calls.append(1)
            raise KeyError("k")

        try:
            solution.retry(fails, attempts=attempts, backoff_s=0.1, max_backoff_s=100.0,
                           retry_on=(KeyError,), sleep=naps.append)
        except KeyError:
            pass
        assert (len(calls), len(naps)) == (attempts, attempts - 1), (
            "args=%r got=%r want=%r" % (attempts, (len(calls), len(naps)),
                                        (attempts, attempts - 1)))
