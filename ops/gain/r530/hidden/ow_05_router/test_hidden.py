"""ow_05_router — hidden checks, 15. **Never enters a workspace.**

Generated from bank/ow_05_router/hidden/*.py by export_bank.py; the
anchor table is in ANCHORS.md beside this file.
"""
import solution


def check_h01_literal_beats_parameter():
    # anchor_kind: goal
    # anchor: they want the same answer every time -- the more specific one
    # derivation: a literal segment is more specific than a named one at the same
    # position, so the literal route answers.


    def _bank_entry(solution):
        router = solution.Router()
        router.add("/orders/{ref}", "one_order")
        router.add("/orders/export", "export_orders")
        got = router.match("/orders/export")
        assert got == ("export_orders", {}), (
            "args=%r got=%r want=%r" % ("/orders/export", got, ("export_orders", {})))
    _bank_entry(solution)


def check_h02_parameter_beats_catch_all():
    # anchor_kind: contract
    # anchor: Rank the segments literal, then `{name}`, then `{name:*}`
    # derivation: a single-segment parameter outranks a rest-of-path capture at the
    # same position.


    def _bank_entry(solution):
        router = solution.Router()
        router.add("/docs/{rest:*}", "docs_tree")
        router.add("/docs/{page}", "docs_page")
        got = router.match("/docs/intro")
        assert got == ("docs_page", {"page": "intro"}), (
            "args=%r got=%r want=%r" % ("/docs/intro", got, ("docs_page", {"page": "intro"})))
        got = router.match("/docs/a/b")
        assert got == ("docs_tree", {"rest": "a/b"}), (
            "args=%r got=%r want=%r" % ("/docs/a/b", got, ("docs_tree", {"rest": "a/b"})))
    _bank_entry(solution)


def check_h03_leftmost_difference_decides():
    # anchor_kind: contract
    # anchor: compare the two patterns segment by segment from the left: the first
    # position at which they differ picks the winner
    # derivation: both patterns have one literal and one parameter, so a rule that
    # counts literals cannot separate them; only the leftmost difference can.


    def _bank_entry(solution):
        router = solution.Router()
        router.add("/{owner}/settings", "user_settings")
        router.add("/admin/{page}", "admin_page")
        got = router.match("/admin/settings")
        assert got == ("admin_page", {"page": "settings"}), (
            "args=%r got=%r want=%r" % ("/admin/settings", got, ("admin_page", {"page": "settings"})))
    _bank_entry(solution)


def check_h04_literal_prefix_beats_bare_catch_all():
    # anchor_kind: contract
    # anchor: the first position at which they differ picks the winner
    # derivation: at the first segment one pattern has a literal and the other a
    # rest-of-path capture, so the literal one wins however long the path is.


    def _bank_entry(solution):
        router = solution.Router()
        router.add("/{anything:*}", "fallback")
        router.add("/media/{rest:*}", "media")
        got = router.match("/media/img/logo/small.png")
        want = ("media", {"rest": "img/logo/small.png"})
        assert got == want, "args=%r got=%r want=%r" % ("/media/img/logo/small.png", got, want)
        got = router.match("/other/thing")
        want = ("fallback", {"anything": "other/thing"})
        assert got == want, "args=%r got=%r want=%r" % ("/other/thing", got, want)
    _bank_entry(solution)


def check_h05_registration_order_irrelevant():
    # anchor_kind: goal
    # anchor: the answer must not depend on that order
    # derivation: every permutation of the same three routes must answer the same way
    # for the same path.

    import itertools


    def _bank_entry(solution):
        routes = [("/p/{id}", "one"), ("/p/latest", "latest"), ("/p/{rest:*}", "tree")]
        answers = []
        for order in itertools.permutations(routes):
            router = solution.Router()
            for pattern, name in order:
                router.add(pattern, name)
            answers.append((router.match("/p/latest"), router.match("/p/9"), router.match("/p/a/b")))
        distinct = sorted(set(repr(answer) for answer in answers))
        assert len(distinct) == 1, "args=%r got=%r want=%r" % (
            "six registration orders", distinct, "one answer for all six")
        got = answers[0]
        want = (("latest", {}), ("one", {"id": "9"}), ("tree", {"rest": "a/b"}))
        assert got == want, "args=%r got=%r want=%r" % ("six registration orders", got, want)
    _bank_entry(solution)


def check_h06_same_pattern_twice():
    # anchor_kind: contract
    # anchor: Two patterns that differ only in their parameter names are the same
    # pattern. Registering the second one raises `ValueError` from `add`.
    # derivation: the parameter name is not part of what makes a pattern distinct, so
    # the second registration is a collision.


    def _bank_entry(solution):
        router = solution.Router()
        router.add("/items/{id}", "first")
        try:
            router.add("/items/{item_id}", "second")
        except ValueError:
            return
        raise AssertionError("args=%r got=%r want=%r"
                             % ("/items/{item_id} after /items/{id}", "no error", "ValueError"))
    _bank_entry(solution)


def check_h07_several_named_pieces():
    # anchor_kind: goal
    # anchor: pulling out the named pieces of the path along the way
    # derivation: every parameter in the pattern appears in the returned mapping, under
    # its own name, holding exactly the text of its segment.


    def _bank_entry(solution):
        router = solution.Router()
        router.add("/{tenant}/repos/{owner}/{repo}/issues/{number}", "issue")
        got = router.match("/acme/repos/bob/tools/issues/318")
        want = ("issue", {"tenant": "acme", "owner": "bob", "repo": "tools", "number": "318"})
        assert got == want, "args=%r got=%r want=%r" % ("/acme/repos/bob/tools/issues/318", got, want)
    _bank_entry(solution)


def check_h08_catch_all_keeps_slashes():
    # anchor_kind: goal
    # anchor: a pattern that swallows the rest of the path for serving files
    # derivation: the captured remainder keeps its slashes, so a nested file path comes
    # back whole.


    def _bank_entry(solution):
        router = solution.Router()
        router.add("/files/{path:*}", "serve")
        got = router.match("/files/a/b/c/d.txt")
        want = ("serve", {"path": "a/b/c/d.txt"})
        assert got == want, "args=%r got=%r want=%r" % ("/files/a/b/c/d.txt", got, want)
    _bank_entry(solution)


def check_h09_parameter_rejects_empty_segment():
    # anchor_kind: contract
    # anchor: `{name}` matches exactly one segment, never spans a `/`, and never matches
    # an empty segment.
    # derivation: a trailing slash leaves an empty segment, which a named segment must
    # refuse rather than capture as "".


    def _bank_entry(solution):
        router = solution.Router()
        router.add("/tags/{tag}", "tag")
        got = router.match("/tags/")
        assert got is None, "args=%r got=%r want=%r" % ("/tags/", got, None)
    _bank_entry(solution)


def check_h10_parameter_does_not_span_slash():
    # anchor_kind: contract
    # anchor: never spans a `/`
    # derivation: a two-segment tail cannot be swallowed by one named segment, so the
    # deeper path does not match the shallower pattern.


    def _bank_entry(solution):
        router = solution.Router()
        router.add("/blog/{slug}", "post")
        got = router.match("/blog/2026/hello")
        assert got is None, "args=%r got=%r want=%r" % ("/blog/2026/hello", got, None)
    _bank_entry(solution)


def check_h11_nobody_owns_it():
    # anchor_kind: goal
    # anchor: A path that belongs to nobody
    # derivation: with routes registered but none fitting, the answer is None rather
    # than an exception or an empty tuple.


    def _bank_entry(solution):
        router = solution.Router()
        router.add("/a/{x}", "a")
        router.add("/b/c", "bc")
        for path in ("/", "/a", "/b", "/a/x/y", "/zzz"):
            got = router.match(path)
            assert got is None, "args=%r got=%r want=%r" % (path, got, None)
    _bank_entry(solution)


def check_h12_matched_with_no_named_pieces():
    # anchor_kind: goal
    # anchor: has to be distinguishable from a path that matched with no named pieces
    # derivation: an all-literal pattern returns an empty mapping, which must not be
    # confused with no match at all.


    def _bank_entry(solution):
        router = solution.Router()
        router.add("/health/live", "liveness")
        got = router.match("/health/live")
        assert got is not None, "args=%r got=%r want=%r" % ("/health/live", got, "a match")
        assert got == ("liveness", {}), (
            "args=%r got=%r want=%r" % ("/health/live", got, ("liveness", {})))
    _bank_entry(solution)


def check_h13_catch_all_must_be_last():
    # anchor_kind: contract
    # anchor: may only appear as the last segment
    # derivation: a rest-of-path capture in the middle is a malformed pattern and is
    # rejected where it is written.


    def _bank_entry(solution):
        router = solution.Router()
        try:
            router.add("/files/{rest:*}/download", "broken")
        except ValueError:
            return
        raise AssertionError("args=%r got=%r want=%r"
                             % ("/files/{rest:*}/download", "no error", "ValueError"))
    _bank_entry(solution)


def check_h14_malformed_patterns():
    # anchor_kind: goal
    # anchor: they want a mistake in a pattern to be reported when the route is
    # registered rather than on the first request that hits it
    # derivation: every malformed shape raises from add, before any path is matched.


    def _bank_entry(solution):
        router = solution.Router()
        for pattern in ("users/{id}", "/users/{}", "/users/{id", "/users/id}", "/a/{b:*}/c"):
            try:
                router.add(pattern, "x")
            except ValueError:
                continue
            raise AssertionError("args=%r got=%r want=%r" % (pattern, "no error", "ValueError"))
    _bank_entry(solution)


def check_h15_catch_all_needs_something():
    # anchor_kind: contract
    # anchor: must not be empty
    # derivation: the rest-of-path capture needs at least one character, so the bare
    # prefix does not match and neither does the prefix with a trailing slash.


    def _bank_entry(solution):
        router = solution.Router()
        router.add("/dl/{path:*}", "download")
        for path in ("/dl", "/dl/"):
            got = router.match(path)
            assert got is None, "args=%r got=%r want=%r" % (path, got, None)
    _bank_entry(solution)
