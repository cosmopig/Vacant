# anchor_kind: goal
# anchor: A subclass of a listed error counts as that error.
# derivation: listing the base class is enough, so a derived failure is retried
# rather than escaping on the first attempt.


class Base(Exception):
    pass


class Derived(Base):
    pass


def run(solution):
    calls = []

    def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise Derived("child")
        return "done"

    got = solution.retry(flaky, attempts=4, backoff_s=0.0, max_backoff_s=0.0,
                         retry_on=(Base,), sleep=lambda _s: None)
    assert got == "done", "args=%r got=%r want=%r" % ("Derived raised, Base listed", got, "done")
    assert len(calls) == 3, "args=%r got=%r want=%r" % ("Derived raised, Base listed", len(calls), 3)
