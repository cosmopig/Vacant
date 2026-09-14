# anchor_kind: contract
# anchor: `plan` returns a list of job names.
# derivation: an empty table gives an empty list, and a table where nothing waits
# for anything still returns every job once.


def run(solution):
    assert solution.plan({}) == [], "args=%r got=%r want=%r" % ({}, solution.plan({}), [])
    jobs = {"a": [], "b": [], "c": []}
    got = solution.plan(jobs)
    assert sorted(got) == ["a", "b", "c"], (
        "args=%r got=%r want=%r" % (jobs, sorted(got), ["a", "b", "c"]))
