"""ow_20_slugify — hidden checks, 7. **Never enters a workspace.**

Generated from bank/ow_20_slugify/hidden/*.py by export_bank.py; the
anchor table is in ANCHORS.md beside this file.
"""
import solution


def check_h01_same_order_same_length():
    # anchor_kind: goal
    # anchor: one slug per title, in the same order as the titles they handed in
    # derivation: the slug for a title stays at that title's index, whatever the other
    # titles in the batch are.


    def _bank_entry(solution):
        titles = ["Zebra Report", "Apple Notes", "Marker Title", "Banana Split"]
        got = solution.slugify(titles)
        assert len(got) == 4, "args=%r got=%r want=%r" % (titles, got, "four slugs")
        assert "marker" in got[2], "args=%r got=%r want=%r" % (titles, got[2], "the marker title's slug")
        assert "zebra" in got[0] and "banana" in got[3], (
            "args=%r got=%r want=%r" % (titles, got, "order kept"))
    _bank_entry(solution)


def check_h02_only_allowed_characters():
    # anchor_kind: goal
    # anchor: a slug holds only lowercase letters, digits and hyphens
    # derivation: titles full of punctuation, capitals, accents and spaces still produce
    # slugs made of nothing but the three allowed kinds of character.

    import re

    ALLOWED = re.compile(r"^[a-z0-9-]+$")


    def _bank_entry(solution):
        titles = ["What's New in 2026?!", "  Spaces   Everywhere  ", "Café & Crème",
                  "MiXeD CaSe", "under_scores/and/slashes", "100% Better"]
        for slug in solution.slugify(titles):
            assert ALLOWED.match(slug), "args=%r got=%r want=%r" % (titles, slug, "only a-z 0-9 -")
    _bank_entry(solution)


def check_h03_hyphen_rules():
    # anchor_kind: goal
    # anchor: never starts or ends with a hyphen, and never has two hyphens in a row
    # derivation: titles that begin, end or are riddled with punctuation still produce
    # slugs obeying all three hyphen rules.


    def _bank_entry(solution):
        titles = ["!!! Breaking News !!!", "-leading and trailing-", "a  --  b",
                  "...", "end.", ".start"]
        for slug in solution.slugify(titles):
            assert not slug.startswith("-"), "args=%r got=%r want=%r" % (titles, slug, "no leading hyphen")
            assert not slug.endswith("-"), "args=%r got=%r want=%r" % (titles, slug, "no trailing hyphen")
            assert "--" not in slug, "args=%r got=%r want=%r" % (titles, slug, "no doubled hyphen")
            assert slug != "", "args=%r got=%r want=%r" % (titles, slug, "not empty")
    _bank_entry(solution)


def check_h04_no_two_the_same():
    # anchor_kind: goal
    # anchor: no two slugs in a batch are the same
    # derivation: identical titles, and different titles that clean down to the same
    # thing, still come back as distinct slugs.


    def _bank_entry(solution):
        titles = ["Same Title", "Same Title", "same title", "SAME TITLE!", "Same  Title"]
        got = solution.slugify(titles)
        assert len(set(got)) == len(got), "args=%r got=%r want=%r" % (titles, got, "five distinct slugs")
        assert len(got) == 5, "args=%r got=%r want=%r" % (titles, got, "five slugs")
    _bank_entry(solution)


def check_h05_same_batch_same_slugs():
    # anchor_kind: goal
    # anchor: handing in the same batch twice gives the same slugs
    # derivation: repeated calls on the same batch return exactly the same list, which a
    # random collision suffix cannot do.


    def _bank_entry(solution):
        titles = ["Post", "Post", "Post", "另一篇", "另一篇"]
        answers = [solution.slugify(titles) for _ in range(4)]
        assert all(answer == answers[0] for answer in answers), (
            "args=%r got=%r want=%r" % (titles, answers, "four identical answers"))
    _bank_entry(solution)


def check_h06_clean_titles_come_back_whole():
    # anchor_kind: goal
    # anchor: a title that is already a clean slug, and that nothing else in the batch
    # collides with, comes back exactly as it was
    # derivation: a batch of titles that are already slugs is returned unchanged, one
    # for one.


    def _bank_entry(solution):
        titles = ["intro-to-widgets", "part-2", "a", "9-lives", "x-y-z"]
        got = solution.slugify(titles)
        assert got == titles, "args=%r got=%r want=%r" % (titles, got, titles)
    _bank_entry(solution)


def check_h07_non_latin_titles():
    # anchor_kind: goal
    # anchor: a title written in a script with no Latin letters in it at all still gets
    # a usable slug rather than an empty one
    # derivation: Chinese, Japanese and Greek titles each produce a non-empty slug that
    # still obeys the character and hyphen rules, and two different such titles do not
    # collide.

    import re

    ALLOWED = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


    def _bank_entry(solution):
        titles = ["台南的老房子", "こんにちは世界", "Καλημέρα", "台北的老房子"]
        got = solution.slugify(titles)
        for slug in got:
            assert slug, "args=%r got=%r want=%r" % (titles, got, "no empty slug")
            assert ALLOWED.match(slug), "args=%r got=%r want=%r" % (titles, slug, "a clean slug")
        assert len(set(got)) == len(got), "args=%r got=%r want=%r" % (titles, got, "all distinct")
    _bank_entry(solution)
