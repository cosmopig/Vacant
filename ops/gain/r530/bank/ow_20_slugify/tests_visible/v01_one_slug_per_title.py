"""Visible check 1: order kept, and an ordinary title becomes an ordinary slug."""

import re

SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def run(solution):
    titles = ["Hello, World!", "Second Post", "Third"]
    got = solution.slugify(titles)
    assert len(got) == len(titles), "args=%r got=%r want=%r" % (titles, got, "three slugs")
    assert got[0] == "hello-world", "args=%r got=%r want=%r" % (titles, got[0], "hello-world")
    for slug in got:
        assert SLUG.match(slug), "args=%r got=%r want=%r" % (titles, slug, "a clean slug")

if __name__ == "__main__":
    import os, sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    import solution
    run(solution)
    print("PASS v01_one_slug_per_title")
