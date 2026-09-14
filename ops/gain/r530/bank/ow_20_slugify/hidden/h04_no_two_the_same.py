# anchor_kind: goal
# anchor: no two slugs in a batch are the same
# derivation: identical titles, and different titles that clean down to the same
# thing, still come back as distinct slugs.


def run(solution):
    titles = ["Same Title", "Same Title", "same title", "SAME TITLE!", "Same  Title"]
    got = solution.slugify(titles)
    assert len(set(got)) == len(got), "args=%r got=%r want=%r" % (titles, got, "five distinct slugs")
    assert len(got) == 5, "args=%r got=%r want=%r" % (titles, got, "five slugs")
