# anchor_kind: goal
# anchor: never starts or ends with a hyphen, and never has two hyphens in a row
# derivation: titles that begin, end or are riddled with punctuation still produce
# slugs obeying all three hyphen rules.


def run(solution):
    titles = ["!!! Breaking News !!!", "-leading and trailing-", "a  --  b",
              "...", "end.", ".start"]
    for slug in solution.slugify(titles):
        assert not slug.startswith("-"), "args=%r got=%r want=%r" % (titles, slug, "no leading hyphen")
        assert not slug.endswith("-"), "args=%r got=%r want=%r" % (titles, slug, "no trailing hyphen")
        assert "--" not in slug, "args=%r got=%r want=%r" % (titles, slug, "no doubled hyphen")
        assert slug != "", "args=%r got=%r want=%r" % (titles, slug, "not empty")
