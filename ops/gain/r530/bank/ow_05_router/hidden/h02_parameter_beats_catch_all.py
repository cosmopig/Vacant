# anchor_kind: contract
# anchor: Rank the segments literal, then `{name}`, then `{name:*}`
# derivation: a single-segment parameter outranks a rest-of-path capture at the
# same position.


def run(solution):
    router = solution.Router()
    router.add("/docs/{rest:*}", "docs_tree")
    router.add("/docs/{page}", "docs_page")
    got = router.match("/docs/intro")
    assert got == ("docs_page", {"page": "intro"}), (
        "args=%r got=%r want=%r" % ("/docs/intro", got, ("docs_page", {"page": "intro"})))
    got = router.match("/docs/a/b")
    assert got == ("docs_tree", {"rest": "a/b"}), (
        "args=%r got=%r want=%r" % ("/docs/a/b", got, ("docs_tree", {"rest": "a/b"})))
