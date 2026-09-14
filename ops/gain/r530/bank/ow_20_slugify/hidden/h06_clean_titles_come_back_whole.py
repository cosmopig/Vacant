# anchor_kind: goal
# anchor: a title that is already a clean slug, and that nothing else in the batch
# collides with, comes back exactly as it was
# derivation: a batch of titles that are already slugs is returned unchanged, one
# for one.


def run(solution):
    titles = ["intro-to-widgets", "part-2", "a", "9-lives", "x-y-z"]
    got = solution.slugify(titles)
    assert got == titles, "args=%r got=%r want=%r" % (titles, got, titles)
