# anchor_kind: goal
# anchor: they want the original error, not something the helper wrapped around it
# derivation: the object that comes out is the very object the last call raised, so
# the caller's own attributes on it survive.


class Flaky(RuntimeError):
    pass


def run(solution):
    mine = Flaky("the real one")
    mine.detail = 7

    def fails():
        raise mine

    try:
        solution.retry(fails, attempts=3, backoff_s=0.0, max_backoff_s=0.0,
                       retry_on=(Flaky,), sleep=lambda _s: None)
    except BaseException as got:
        assert got is mine, "args=%r got=%r want=%r" % ("a Flaky instance", got, mine)
        assert getattr(got, "detail", None) == 7, (
            "args=%r got=%r want=%r" % ("a Flaky instance", getattr(got, "detail", None), 7))
        return
    raise AssertionError("args=%r got=%r want=%r" % ("a Flaky instance", "returned", "Flaky"))
