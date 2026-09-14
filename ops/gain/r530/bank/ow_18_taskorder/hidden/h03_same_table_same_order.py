# anchor_kind: goal
# anchor: running the planner twice on the same table gives the same order
# derivation: repeated calls on the same table return exactly the same list, so the
# build log diffs cleanly.


def run(solution):
    jobs = {"x": [], "y": [], "z": ["x", "y"], "w": []}
    answers = [solution.plan(jobs) for _ in range(5)]
    assert all(answer == answers[0] for answer in answers), (
        "args=%r got=%r want=%r" % (jobs, answers, "five identical orders"))
