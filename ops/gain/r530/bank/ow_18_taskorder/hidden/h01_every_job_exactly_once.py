# anchor_kind: goal
# anchor: every job appears in the order exactly once, and a job that is only ever
# mentioned as something else's prerequisite is still a job
# derivation: the order is a permutation of every name that appears anywhere in the
# table, keys and prerequisites alike.


def run(solution):
    jobs = {"c": ["a", "b"], "d": ["c"], "e": []}
    got = solution.plan(jobs)
    want = ["a", "b", "c", "d", "e"]
    assert sorted(got) == want, "args=%r got=%r want=%r" % (jobs, sorted(got), want)
    assert len(got) == len(set(got)), "args=%r got=%r want=%r" % (jobs, got, "no repeats")
