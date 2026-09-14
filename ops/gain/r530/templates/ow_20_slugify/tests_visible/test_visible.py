"""Checks that ship with this task. You can run them yourself: `sh run_tests.sh`.

Each `check_*` function is one check. A check passes when it returns
normally. These are the same checks the client runs before accepting
the work.
"""
import solution


def check_v01_one_slug_per_title():
    """Visible check 1: order kept, and an ordinary title becomes an ordinary slug."""

    import re

    SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


    def _bank_entry(solution):
        titles = ["Hello, World!", "Second Post", "Third"]
        got = solution.slugify(titles)
        assert len(got) == len(titles), "args=%r got=%r want=%r" % (titles, got, "three slugs")
        assert got[0] == "hello-world", "args=%r got=%r want=%r" % (titles, got[0], "hello-world")
        for slug in got:
            assert SLUG.match(slug), "args=%r got=%r want=%r" % (titles, slug, "a clean slug")
    _bank_entry(solution)


def check_v02_already_a_slug():
    """Visible check 2: a title that is already a clean slug is left alone."""


    def _bank_entry(solution):
        titles = ["already-a-slug", "another-one", "third-thing"]
        got = solution.slugify(titles)
        assert got == titles, "args=%r got=%r want=%r" % (titles, got, titles)
    _bank_entry(solution)
