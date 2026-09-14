# anchor_kind: goal
# anchor: a slug holds only lowercase letters, digits and hyphens
# derivation: titles full of punctuation, capitals, accents and spaces still produce
# slugs made of nothing but the three allowed kinds of character.

import re

ALLOWED = re.compile(r"^[a-z0-9-]+$")


def run(solution):
    titles = ["What's New in 2026?!", "  Spaces   Everywhere  ", "Café & Crème",
              "MiXeD CaSe", "under_scores/and/slashes", "100% Better"]
    for slug in solution.slugify(titles):
        assert ALLOWED.match(slug), "args=%r got=%r want=%r" % (titles, slug, "only a-z 0-9 -")
