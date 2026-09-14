# anchor_kind: goal
# anchor: because some jobs wait on each other in a circle, directly or through
# others
# derivation: a two-job circle and a longer one both raise, including when other
# jobs in the table could have been ordered perfectly well.


def run(solution):
    for jobs in ({"a": ["b"], "b": ["c"], "c": ["a"]},
                 {"ok": [], "a": ["b"], "b": ["a"], "also_ok": ["ok"]},
                 {"a": ["b"], "b": ["c"], "c": ["d"], "d": ["b"]}):
        try:
            solution.plan(jobs)
        except ValueError:
            continue
        raise AssertionError("args=%r got=%r want=%r" % (jobs, "an order", "ValueError"))
