# anchor_kind: goal
# anchor: handing in the same batch twice gives the same slugs
# derivation: repeated calls on the same batch return exactly the same list, which a
# random collision suffix cannot do.


def run(solution):
    titles = ["Post", "Post", "Post", "另一篇", "另一篇"]
    answers = [solution.slugify(titles) for _ in range(4)]
    assert all(answer == answers[0] for answer in answers), (
        "args=%r got=%r want=%r" % (titles, answers, "four identical answers"))
