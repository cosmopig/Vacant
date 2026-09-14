# anchor_kind: goal
# anchor: nothing runs before something it waits for
# derivation: for every job and every one of its prerequisites, the prerequisite
# stands earlier in the order.


def run(solution):
    jobs = {"app": ["lib", "assets"], "lib": ["proto"], "assets": ["proto"],
            "proto": [], "docs": ["app"], "package": ["app", "docs"]}
    got = solution.plan(jobs)
    position = dict((name, index) for index, name in enumerate(got))
    for name, needs in jobs.items():
        for need in needs:
            assert position[need] < position[name], (
                "args=%r got=%r want=%r" % (jobs, got, "%s before %s" % (need, name)))
