# anchor_kind: goal
# anchor: a title written in a script with no Latin letters in it at all still gets
# a usable slug rather than an empty one
# derivation: Chinese, Japanese and Greek titles each produce a non-empty slug that
# still obeys the character and hyphen rules, and two different such titles do not
# collide.

import re

ALLOWED = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def run(solution):
    titles = ["台南的老房子", "こんにちは世界", "Καλημέρα", "台北的老房子"]
    got = solution.slugify(titles)
    for slug in got:
        assert slug, "args=%r got=%r want=%r" % (titles, got, "no empty slug")
        assert ALLOWED.match(slug), "args=%r got=%r want=%r" % (titles, slug, "a clean slug")
    assert len(set(got)) == len(got), "args=%r got=%r want=%r" % (titles, got, "all distinct")
