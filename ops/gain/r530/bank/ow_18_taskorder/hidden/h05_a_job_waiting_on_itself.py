# anchor_kind: goal
# anchor: or because a job waits on itself
# derivation: a job listing its own name can never start, so the table is reported
# rather than ordered.


def run(solution):
    for jobs in ({"a": ["a"]}, {"a": [], "b": ["b"], "c": ["a"]}):
        try:
            solution.plan(jobs)
        except ValueError:
            continue
        raise AssertionError("args=%r got=%r want=%r" % (jobs, "an order", "ValueError"))
